from typing import Any

from pydantic import BaseModel


class ScoreRequest(BaseModel):
    resume: dict[str, Any]
    job_description: str | None = None


class ResumeIn(BaseModel):
    basics: dict[str, Any]
    work: list[dict[str, Any]] = []
    education: list[dict[str, Any]] = []
    projects: list[dict[str, Any]] = []
    skills: list[str] = []
    certifications: list[str] = []
    id: str | None = None
