"""Postgres schema. Firebase UID is the identity key; all app data hangs off users."""
import uuid
from datetime import datetime

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
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


class SuggestionCache(Base):
    """Cached LLM suggestions, keyed by a hash of (resume text, job description).

    Exists to stop paying Groq for a request we have already answered — the live
    editor re-scores on every edit, and most of those edits do not change the
    advice. See app/services/llm_cache.py for the key derivation and the TTL.

    PRIVACY: `cache_key` is a hash, but `suggestions` is feedback written about a
    real resume, and `user_id` links it to a person. These rows are user data and
    DELETE /users/me removes them. Anonymous rows carry user_id NULL and expire by
    TTL instead.
    """
    __tablename__ = "suggestion_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    cache_key: Mapped[str] = mapped_column(String, unique=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    suggestions: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class LlmUsage(Base):
    """One row per (caller, UTC day) counting LLM calls, for the daily cap.

    `subject` is "user:<id>" for signed-in callers and "ip:<address>" for anonymous
    ones. Counting in Postgres rather than in memory because the free-tier quota is
    shared across every worker process, and an in-memory counter resets on deploy —
    which is exactly when a burst would blow the quota.
    """
    __tablename__ = "llm_usage"
    __table_args__ = (UniqueConstraint("subject", "day", name="uq_llm_usage_subject_day"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    subject: Mapped[str] = mapped_column(String, index=True)
    day: Mapped[str] = mapped_column(String, index=True)  # "YYYY-MM-DD", UTC
    count: Mapped[int] = mapped_column(Integer, default=0)


class TrainingExample(Base):
    """Consented (resume, LLM score/suggestions) pairs — the JEPA distillation dataset (Phase 4)."""
    __tablename__ = "training_examples"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(ForeignKey("score_reports.id"), index=True)
    anonymized_resume: Mapped[dict] = mapped_column(JSON)  # PII stripped before storage
    teacher_output: Mapped[dict] = mapped_column(JSON)  # LLM score + suggestions
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OnetSkill(Base):
    """O*NET's (occupation, skill, importance) rows — see scripts/ingest_onet.py for
    provenance and licensing. `embedding` is filled in by a later migration once
    pgvector is enabled; NULL until then, and skills_rag falls back to keyword
    matching for any row without one.
    """
    __tablename__ = "onet_skills"
    __table_args__ = (UniqueConstraint("occupation", "skill", name="uq_onet_skill"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    occupation: Mapped[str] = mapped_column(String, index=True)
    skill: Mapped[str] = mapped_column(String, index=True)
    importance: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String)  # "skills" | "technology_skills"
