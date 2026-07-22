"""Postgres schema. Firebase UID is the identity key; all app data hangs off users."""
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    firebase_uid: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # Explicit consent for using resume data in model training (JEPA distillation).
    training_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    resumes: Mapped[list["ResumeRecord"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class ResumeRecord(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    data: Mapped[dict] = mapped_column(JSON)  # JSON Resume schema document
    template: Mapped[str] = mapped_column(String, default="clean")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="resumes")
    reports: Mapped[list["ScoreReportRecord"]] = relationship(back_populates="resume", cascade="all, delete-orphan")


class ScoreReportRecord(Base):
    __tablename__ = "score_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    resume_id: Mapped[str | None] = mapped_column(ForeignKey("resumes.id"), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    job_title: Mapped[str | None] = mapped_column(String, nullable=True)
    job_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    total: Mapped[float] = mapped_column(Float)
    payload: Mapped[dict] = mapped_column(JSON)  # full report: categories, suggestions, missing skills
    scorer: Mapped[str] = mapped_column(String, default="stub")  # stub | bm25_sbert | llm | jepa
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    resume: Mapped["ResumeRecord | None"] = relationship(back_populates="reports")


class TrainingExample(Base):
    """Consented (resume, LLM score/suggestions) pairs — the JEPA distillation dataset (Phase 4)."""
    __tablename__ = "training_examples"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(ForeignKey("score_reports.id"), index=True)
    anonymized_resume: Mapped[dict] = mapped_column(JSON)  # PII stripped before storage
    teacher_output: Mapped[dict] = mapped_column(JSON)  # LLM score + suggestions
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
