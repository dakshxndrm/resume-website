import json
import uuid
from datetime import datetime, timezone

from fastapi import (APIRouter, Depends, File, Form, HTTPException, Request, Response,
                     UploadFile)
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.schemas import ConsentIn, ResumeIn, ScoreRequest
from app.core.auth import get_current_user, get_optional_user
from app.core.config import settings
from app.core.db import get_db
from app.models.models import ResumeRecord, ScoreReportRecord, TrainingExample, User
from app.services import llm_cache
from app.services.llm_router import generate_suggestions, llm_enabled, ping
from app.services.parsing import parse_resume
from app.services.pdf_export import build_resume_pdf, is_empty_resume, safe_filename
from app.services.privacy import anonymize_resume
from app.services.scoring import score_resume

router = APIRouter()


def _client_ip(request: Request) -> str | None:
    """Caller IP for the anonymous rate-limit bucket.

    X-Forwarded-For first because the app runs behind Railway/Render's proxy, where
    request.client.host is the proxy, not the user. Take the leftmost entry — the
    original client. It is spoofable by a determined caller; this limit protects a
    shared free-tier quota from ordinary traffic, not from an attacker.
    ponytail: trust the header, tighten to a trusted-proxy count if abuse shows up.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _now_iso() -> str:
    """UTC timestamp, same naive-ISO shape the API has always returned.

    datetime.utcnow() is deprecated; now(timezone.utc) is the replacement but adds
    a '+00:00' suffix. Dropping the tzinfo keeps the wire format byte-identical for
    existing clients. ponytail: emit real offset-aware ISO when the frontend is
    ready to parse it.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


# ---------- LLM suggestion swap ----------
def _resume_to_text(resume: dict) -> str:
    """Flatten a structured resume into text for the LLM prompt."""
    return json.dumps(resume, ensure_ascii=False)


def _apply_llm_suggestions(result: dict, resume_text: str, job_description: str | None,
                           db: Session | None = None, user: User | None = None,
                           client_ip: str | None = None) -> dict:
    """Swap in AI suggestions if we can get any; otherwise keep the rule-based ones.

    Order is cheapest-first, and every step degrades to the step below it:

      1. cache hit          -> suggestionsSource "cache", no Groq call at all
      2. LLM off / cooling  -> "rules"
      3. over the daily cap -> "rules"
      4. Groq answers       -> "ai", and the answer is cached for next time
      5. anything else      -> "rules"

    `db` is optional so the function still works uncached — every cache and
    rate-limit operation is best-effort and cannot break scoring.
    """
    key = None
    if db is not None:
        try:
            key = llm_cache.cache_key(resume_text, job_description)
            cached = llm_cache.get_cached(db, key)
            if cached:
                return {**result, "suggestions": cached, "suggestionsSource": "cache"}
        except Exception as exc:  # a broken cache is a cache miss, nothing more
            print(f"WARNING: suggestion cache lookup failed: {type(exc).__name__}: {exc}")
            key = None

    if not llm_enabled():
        return {**result, "suggestionsSource": "rules"}

    user_id = user.id if user else None
    if db is not None:
        try:
            if not llm_cache.within_limit(db, user_id, client_ip):
                # Over the daily cap: a real report with rule-based advice, never
                # an error and never a fabricated score.
                return {**result, "suggestionsSource": "rules"}
            llm_cache.record_call(db, user_id, client_ip)
        except Exception as exc:
            print(f"WARNING: rate-limit check failed: {type(exc).__name__}: {exc}")

    ai = generate_suggestions(resume_text, job_description, result)
    if not ai:
        return {**result, "suggestionsSource": "rules"}

    if db is not None and key:
        llm_cache.put_cached(db, key, ai, user_id)
    return {**result, "suggestions": ai, "suggestionsSource": "ai"}


def _log_training_example(db: Session, user: User | None, report_id: str,
                          resume: dict, result: dict) -> bool:
    """Store a consented (anonymised resume, teacher output) pair for Phase 4 JEPA.

    The single gate for the whole training dataset: no user row, or
    training_consent False, means nothing is written. Consent is checked here and
    nowhere else, so there is exactly one place to audit.

    Best-effort like the report save — a failure here must never cost the user
    their score. Returns whether a row was written (used by tests).
    """
    if user is None or not user.training_consent:
        return False
    try:
        db.add(TrainingExample(
            report_id=report_id,
            anonymized_resume=anonymize_resume(resume, known=[user.name or "", user.email or ""]),
            teacher_output={"total": result["total"],
                            "categories": result["categories"],
                            "suggestions": result["suggestions"],
                            "source": result.get("suggestionsSource")},
        ))
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        print(f"WARNING: could not log training example for {report_id}: "
              f"{type(exc).__name__}: {exc}")
        return False


def _job_title(job_description: str | None) -> str | None:
    """Short display label for the report — the full JD is stored separately."""
    first_line = (job_description or "").strip().splitlines()[0].strip() if job_description else ""
    if not first_line:
        return None
    return first_line if len(first_line) <= 80 else first_line[:77] + "..."


# ---------- auth ----------
@router.post("/auth/sync")
def sync_user(claims: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create/refresh the Postgres user row for this Firebase identity."""
    user = db.query(User).filter_by(firebase_uid=claims["uid"]).first()
    if not user:
        user = User(
            firebase_uid=claims["uid"],
            email=claims.get("email", ""),
            name=claims.get("name"),
            photo_url=claims.get("picture"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return {"id": user.id}


def _require_user(claims: dict, db: Session) -> User:
    user = db.query(User).filter_by(firebase_uid=claims["uid"]).first()
    if not user:
        raise HTTPException(404, "User not synced — call /auth/sync first")
    return user


# ---------- account, consent and deletion (Phase 0) ----------
@router.get("/users/me")
def get_me(claims: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Account state, including the current consent value.

    The consent checkbox has to render the *stored* answer. Without this it would
    render unchecked every time, which would quietly misrepresent a user who had
    already opted in.
    """
    user = _require_user(claims, db)
    return {"id": user.id, "email": user.email, "name": user.name,
            "trainingConsent": user.training_consent}


@router.patch("/users/consent")
def set_consent(body: ConsentIn, claims: dict = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """Turn training consent on or off. Symmetric on purpose — withdrawing is one
    call, exactly like granting. Nothing else about the product changes either way."""
    user = _require_user(claims, db)
    user.training_consent = body.training_consent
    db.commit()
    return {"trainingConsent": user.training_consent}


@router.delete("/users/me")
def delete_me(claims: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Erase everything belonging to this user, children before parents.

    Order matters — training_examples -> cached suggestions -> score_reports ->
    resumes -> user — because each step's rows point at the next one's. Reports are
    matched by user_id *and* by resume, so a report attached only to a resume is not
    left orphaned.

    One transaction: a partial delete would be worse than none, because the user
    would be told their data is gone when some of it is not.
    """
    user = _require_user(claims, db)

    resume_ids = [r.id for r in db.query(ResumeRecord).filter_by(user_id=user.id).all()]
    owned = [ScoreReportRecord.user_id == user.id]
    if resume_ids:
        owned.append(ScoreReportRecord.resume_id.in_(resume_ids))
    reports = db.query(ScoreReportRecord).filter(or_(*owned)).all()
    report_ids = [r.id for r in reports]

    deleted = {"trainingExamples": 0, "scoreReports": len(report_ids),
               "resumes": len(resume_ids), "cachedSuggestions": 0}
    try:
        if report_ids:
            deleted["trainingExamples"] = db.query(TrainingExample).filter(
                TrainingExample.report_id.in_(report_ids)
            ).delete(synchronize_session=False)
        # Cached suggestions are feedback written about this person's resume, so
        # they are user data and go with the rest of it.
        deleted["cachedSuggestions"] = llm_cache.purge_for_user(db, user.id)
        for report in reports:
            db.delete(report)
        for resume in db.query(ResumeRecord).filter_by(user_id=user.id).all():
            db.delete(resume)
        db.delete(user)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, f"Could not delete your data: {type(exc).__name__}") from exc

    return {"deleted": deleted}


# ---------- scoring ----------
@router.post("/score")
def score(req: ScoreRequest, request: Request,
          claims: dict | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    """Score a structured resume. Works logged-out (frictionless); persists when logged in."""
    result = score_resume(req.resume, req.job_description)
    user = db.query(User).filter_by(firebase_uid=claims["uid"]).first() if claims else None
    result = _apply_llm_suggestions(result, _resume_to_text(req.resume), req.job_description,
                                    db=db, user=user, client_ip=_client_ip(request))
    report_id = str(uuid.uuid4())
    payload = {**result, "id": report_id, "jobTitle": _job_title(req.job_description),
               "createdAt": _now_iso()}

    if claims:
        db.add(ScoreReportRecord(
            id=report_id, user_id=user.id if user else None,
            job_title=_job_title(req.job_description),
            job_description=req.job_description, total=result["total"],
            payload=payload, scorer=result["suggestionsSource"],
        ))
        db.commit()
        # only with explicit opt-in; see _log_training_example
        _log_training_example(db, user, report_id, req.resume, payload)
    return payload


@router.post("/score/upload")
async def score_upload(
    request: Request,
    file: UploadFile = File(...),
    job_description: str | None = Form(None),
    claims: dict | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Upload a resume file (PDF/DOCX) for parsing + scoring."""
    parsed = parse_resume(await file.read(), file.filename or "")

    # No extracted text = we never actually read the file (scanned/image-only PDF,
    # legacy .doc, or a corrupt upload). Say so instead of scoring an empty resume.
    if not parsed["raw_text"].strip():
        raise HTTPException(422, (
            "Could not read any text from that file. If it is a scanned or image-only "
            "PDF, or a legacy .doc, please re-save it as a text-based PDF or .docx."
        ))

    # Attach the report to the signed-in user when there is one, so "delete my data"
    # can actually find it later. Anonymous uploads stay unattached, as before.
    user = db.query(User).filter_by(firebase_uid=claims["uid"]).first() if claims else None

    result = score_resume(parsed, job_description)
    result = _apply_llm_suggestions(result, parsed["raw_text"], job_description,
                                    db=db, user=user, client_ip=_client_ip(request))
    report_id = str(uuid.uuid4())
    payload = {**result, "id": report_id, "jobTitle": _job_title(job_description),
               "createdAt": _now_iso()}

    # Persistence is best-effort: a DB hiccup must not throw away a finished report.
    try:
        db.add(ScoreReportRecord(
            id=report_id, user_id=user.id if user else None,
            job_title=_job_title(job_description),
            job_description=job_description, total=result["total"],
            payload=payload, scorer=result["suggestionsSource"],
        ))
        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"WARNING: could not save report {report_id}: {type(exc).__name__}: {exc}")
    else:
        # only with explicit opt-in; see _log_training_example
        _log_training_example(db, user, report_id, parsed, payload)

    # report_id kept alongside the full report so existing callers keep working.
    return {**payload, "report_id": report_id}


@router.get("/report/{report_id}")
def get_report(report_id: str, db: Session = Depends(get_db)):
    rec = db.get(ScoreReportRecord, report_id)
    if not rec:
        raise HTTPException(404, "Report not found")
    return rec.payload


# ---------- export ----------
# Deliberately unauthenticated: editing works logged-out, so exporting must too.
# Nothing is read from or written to the database here — the resume is in the body.
@router.post("/resumes/export")
def export_resume(body: ResumeIn):
    """Render a structured resume to an ATS-friendly, single-column, real-text PDF."""
    resume = body.model_dump(exclude={"id"})
    if is_empty_resume(resume):
        raise HTTPException(422, "Nothing to export yet — add your name or a section first.")

    pdf = build_resume_pdf(resume)
    filename = safe_filename(str((resume.get("basics") or {}).get("name") or "resume"))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- resumes (auth required) ----------
@router.post("/resumes")
def save_resume(body: ResumeIn, claims: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = _require_user(claims, db)
    data = body.model_dump(exclude={"id"})
    if body.id:
        rec = db.get(ResumeRecord, body.id)
        if not rec or rec.user_id != user.id:
            raise HTTPException(404, "Resume not found")
        rec.data = data
    else:
        rec = ResumeRecord(user_id=user.id, data=data)
        db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id}


@router.get("/resumes")
def list_resumes(claims: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = _require_user(claims, db)
    return [{"id": r.id, **r.data} for r in user.resumes]


@router.get("/resumes/{resume_id}")
def get_resume(resume_id: str, claims: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = _require_user(claims, db)
    rec = db.get(ResumeRecord, resume_id)
    if not rec or rec.user_id != user.id:
        raise HTTPException(404, "Resume not found")
    return {"id": rec.id, **rec.data}


# ---------- skills (RAG over O*NET/ESCO — Phase 2) ----------
_STUB_SKILLS = {
    "frontend developer": ["React", "TypeScript", "Next.js", "Tailwind CSS", "Jest", "Accessibility"],
    "backend developer": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "CI/CD"],
}


@router.get("/skills/suggest")
def suggest_skills(role: str):
    return {"skills": _STUB_SKILLS.get(role.lower(), ["Communication", "Git", "Problem Solving"])}


# ---------- debug ----------
@router.get("/llm/health")
def llm_health():
    """Is Groq reachable and is the model name valid? Never echoes the API key."""
    if not (settings.groq_api_key or "").strip():
        return {"llm": "disabled"}
    error = ping()
    if error:
        return {"llm": "error", "model": settings.groq_model, "detail": error}
    return {"llm": "ok", "model": settings.groq_model}
