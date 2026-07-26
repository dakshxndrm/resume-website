from typing import Any

from pydantic import BaseModel


class ScoreRequest(BaseModel):
    resume: dict[str, Any]
    job_description: str | None = None


class ConsentIn(BaseModel):
    """Opt-in for using this user's resume data to train the scoring model.

    No default: the client must say true or false explicitly. A default of False
    would be harmless, but a default of True would be a dark pattern waiting to
    happen, and "no default" makes the intent unmistakable at the call site.
    """
    training_consent: bool


class ResumeIn(BaseModel):
    basics: dict[str, Any]
    work: list[dict[str, Any]] = []
    education: list[dict[str, Any]] = []
    projects: list[dict[str, Any]] = []
    skills: list[str] = []
    certifications: list[str] = []
    id: str | None = None
