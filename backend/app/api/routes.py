import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.schemas import ResumeIn, ScoreRequest
from app.core.auth import get_current_user, get_optional_user
from app.core.db import get_db
from app.models.models import ResumeRecord, ScoreReportRecord, User
from app.services.parsing import parse_resume
from app.services.scoring import score_resume

router = APIRouter()


def _save_report_safe(db: Session, **kwargs) -> None:
    """Persist a report if a DB is reachable. During early dev (no DB yet) we
    simply skip saving instead of crashing the request."""
    try:
        db.add(ScoreReportRecord(**kwargs))
        db.commit()
    except Exception:
        db.rollback()  # no DB / not migrated yet — fine, report still returned to user


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
    report_id = str(uuid.uuid4())
    payload = {**result, "id": report_id, "jobTitle": req.job_description, "createdAt": datetime.utcnow().isoformat()}

    user_id = None
    if claims:
        user = db.query(User).filter_by(firebase_uid=claims["uid"]).first()
        user_id = user.id if user else None
    _save_report_safe(
        db, id=report_id, user_id=user_id, job_description=req.job_description,
        total=result["total"], payload=payload, scorer="phase1",
    )
    return payload


@router.post("/score/upload")
async def score_upload(
    file: UploadFile = File(...),
    job_description: str | None = Form(None),
    claims: dict | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Upload a resume file → parse (PyMuPDF/python-docx) → score against the job description.

    Returns the FULL report so the frontend can show it immediately, even before a
    database is configured (persistence is best-effort until then).
    """
    raw = await file.read()
    parsed = parse_resume(raw, file.filename or "")

    if not parsed.get("raw_text", "").strip():
        raise HTTPException(422, "Could not read that file. Please upload a text-based PDF or DOCX.")

    result = score_resume(parsed, job_description)
    report_id = str(uuid.uuid4())
    payload = {**result, "id": report_id, "jobTitle": job_description, "createdAt": datetime.utcnow().isoformat()}

    user_id = None
    if claims:
        user = db.query(User).filter_by(firebase_uid=claims["uid"]).first()
        user_id = user.id if user else None
    _save_report_safe(
        db, id=report_id, user_id=user_id, job_description=job_description,
        total=result["total"], payload=payload, scorer="phase1",
    )
    return payload  # full report, not just an id


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
