import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.schemas import ResumeIn, ScoreRequest
from app.core.auth import get_current_user, get_optional_user
from app.core.config import settings
from app.core.db import get_db
from app.models.models import ResumeRecord, ScoreReportRecord, User
from app.services.llm_router import generate_suggestions, ping
from app.services.scoring import score_resume

router = APIRouter()


# ---------- LLM suggestion swap ----------
def _resume_to_text(resume: dict) -> str:
    """Flatten a structured resume into text for the LLM prompt."""
    return json.dumps(resume, ensure_ascii=False)


def _apply_llm_suggestions(result: dict, resume_text: str, job_description: str | None) -> dict:
    """Swap in AI suggestions if we got any; otherwise keep the rule-based ones."""
    ai = generate_suggestions(resume_text, job_description, result)
    if ai:
        return {**result, "suggestions": ai, "suggestionsSource": "ai"}
    return {**result, "suggestionsSource": "rules"}


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


# ---------- scoring ----------
@router.post("/score")
def score(req: ScoreRequest, claims: dict | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    """Score a structured resume. Works logged-out (frictionless); persists when logged in."""
    result = score_resume(req.resume, req.job_description)
    result = _apply_llm_suggestions(result, _resume_to_text(req.resume), req.job_description)
    report_id = str(uuid.uuid4())
    payload = {**result, "id": report_id, "jobTitle": req.job_description, "createdAt": datetime.utcnow().isoformat()}

    if claims:
        user = db.query(User).filter_by(firebase_uid=claims["uid"]).first()
        db.add(ScoreReportRecord(
            id=report_id, user_id=user.id if user else None,
            job_description=req.job_description, total=result["total"],
            payload=payload, scorer="stub",
        ))
        db.commit()
    return payload


@router.post("/score/upload")
async def score_upload(
    file: UploadFile = File(...),
    job_description: str | None = Form(None),
    claims: dict | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Upload a resume file (PDF/DOCX) for parsing + scoring."""
    try:
        # lazy import: parsing.py needs PyMuPDF + python-docx, so a missing
        # install breaks only this endpoint instead of the whole app
        from app.services.parsing import parse_resume
    except ImportError as exc:
        raise HTTPException(503, f"File parsing unavailable - pip install PyMuPDF python-docx ({exc})")

    parsed = parse_resume(await file.read(), file.filename or "")
    result = score_resume(parsed, job_description)
    result = _apply_llm_suggestions(result, parsed["raw_text"], job_description)
    report_id = str(uuid.uuid4())
    payload = {**result, "id": report_id, "jobTitle": job_description, "createdAt": datetime.utcnow().isoformat()}
    db.add(ScoreReportRecord(id=report_id, job_description=job_description, total=result["total"], payload=payload, scorer="stub"))
    db.commit()
    return {"report_id": report_id}


@router.get("/report/{report_id}")
def get_report(report_id: str, db: Session = Depends(get_db)):
    rec = db.get(ScoreReportRecord, report_id)
    if not rec:
        raise HTTPException(404, "Report not found")
    return rec.payload


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
