"""Scoring service — Phase 1 (real signals).

Upgraded from the earlier stub: skills, experience, education and projects now
come from the real parsed resume, and the semantic score is a real keyword-
coverage / BM25 relevance of the resume text against the job description.

Weighted formula (per docs/PROJECT_PLAN.md):
  skills 30 · experience 25 · semantic 20 · projects 10 · education 10 · formatting 5

Phase 5 swaps the semantic scorer to Sentence-BERT, then the distilled JEPA.
"""
from __future__ import annotations

import re
from typing import Any

from rank_bm25 import BM25Okapi

from app.services.parsing import SKILL_VOCAB, _pretty_skill

WEIGHTS = {
    "skills": 0.30,
    "experience": 0.25,
    "semantic": 0.20,
    "projects": 0.10,
    "education": 0.10,
    "formatting": 0.05,
}

_LABELS = {
    "skills": "Skills", "experience": "Experience", "semantic": "Semantic match",
    "projects": "Projects", "education": "Education", "formatting": "Formatting",
}


_STOPWORDS = {
    "a", "an", "and", "the", "or", "for", "of", "to", "in", "on", "with",
    "we", "you", "your", "our", "is", "are", "be", "as", "at", "by", "this",
    "that", "will", "who", "have", "has", "need", "looking", "seeking", "must",
    "should", "role", "job", "work", "team", "skilled", "experience", "years",
}


def _tokens(text: str) -> list[str]:
    """Meaningful lowercase tokens (drops common filler words)."""
    raw = re.findall(r"[a-z0-9+#.]+", (text or "").lower())
    return [t for t in raw if t not in _STOPWORDS and len(t) > 1]


def _skills_in(text: str) -> set[str]:
    low = (text or "").lower()
    out: set[str] = set()
    for skill in SKILL_VOCAB:
        if re.search(r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])", low):
            out.add(skill)
    return out


def _semantic_score(resume_text: str, job_description: str | None) -> int:
    """Real relevance of resume text to the job description.

    No JD → neutral 60 (can't compare). With a JD → BM25 relevance of the resume
    against the JD, blended with plain keyword coverage, scaled to 0–100.
    """
    if not job_description or not resume_text.strip():
        return 60

    jd_tokens = _tokens(job_description)
    resume_tokens = _tokens(resume_text)
    if not jd_tokens or not resume_tokens:
        return 60

    # keyword coverage: what share of JD words appear in the resume
    jd_set = set(jd_tokens)
    coverage = len(jd_set & set(resume_tokens)) / len(jd_set)

    # BM25 relevance of the resume (as the single doc) to the JD query
    bm25 = BM25Okapi([resume_tokens])
    raw = bm25.get_scores(jd_tokens)[0]
    # normalise: BM25 grows with matched-query length; divide by query length
    bm25_norm = min(1.0, raw / max(1, len(jd_tokens)))

    blended = 0.6 * coverage + 0.4 * bm25_norm
    return int(round(min(100, blended * 100)))


def _missing_skills(resume_text: str, job_description: str | None) -> list[str]:
    if not job_description:
        return []
    jd_skills = _skills_in(job_description)
    have = _skills_in(resume_text)
    return [_pretty_skill(s) for s in sorted(jd_skills - have)]


def score_resume(resume: dict[str, Any], job_description: str | None = None) -> dict[str, Any]:
    skills = resume.get("skills", [])
    work = resume.get("work", [])
    education = resume.get("education", [])
    projects = resume.get("projects", [])
    raw_text = resume.get("raw_text", "")
    word_count = resume.get("word_count") or len(raw_text.split())

    semantic = _semantic_score(raw_text, job_description)

    # formatting heuristic: penalise too-short / too-long resumes
    if word_count == 0:
        formatting = 50
    elif word_count < 150:
        formatting = 60
    elif word_count > 1200:
        formatting = 70
    else:
        formatting = 85

    cat_scores = {
        "skills": min(100, 25 + len(skills) * 8),
        "experience": min(100, 30 + len(work) * 22),
        "semantic": semantic,
        "projects": min(100, 25 + len(projects) * 25),
        "education": min(100, 40 + len(education) * 30),
        "formatting": formatting,
    }
    total = round(sum(cat_scores[k] * w for k, w in WEIGHTS.items()))

    return {
        "total": total,
        "verdict": _verdict(total),
        "categories": [
            {"key": k, "label": _LABELS[k], "score": cat_scores[k], "weight": w}
            for k, w in WEIGHTS.items()
        ],
        "suggestions": _suggestions(cat_scores, _missing_skills(raw_text, job_description)),
        "missingSkills": _missing_skills(raw_text, job_description),
    }


def _verdict(total: int) -> str:
    if total >= 80:
        return "Strong resume — a few refinements left"
    if total >= 60:
        return "Good foundation — several fixes found"
    return "Needs work — but every issue below is fixable"


def _suggestions(cat_scores: dict[str, int], missing: list[str]) -> list[dict]:
    out: list[dict] = []
    if missing:
        out.append({
            "id": "s-skills", "severity": "high", "category": "skills",
            "title": "Add missing role-critical skills",
            "why": f"The job asks for {', '.join(missing[:5])} — not found in your resume.",
        })
    elif cat_scores["skills"] < 70:
        out.append({
            "id": "s-skills2", "severity": "high", "category": "skills",
            "title": "Add more role-relevant skills",
            "why": "Your skills section is thin — ATS keyword matching weighs it heavily.",
        })
    if cat_scores["experience"] < 70:
        out.append({
            "id": "s-exp", "severity": "high", "category": "experience",
            "title": "Expand your work experience",
            "why": "Add measurable achievements with numbers to each role.",
        })
    if cat_scores["semantic"] < 65:
        out.append({
            "id": "s-sem", "severity": "medium", "category": "semantic",
            "title": "Tailor wording to the job description",
            "why": "Your resume language doesn't closely match the posting — mirror its key terms.",
        })
    if cat_scores["formatting"] < 75:
        out.append({
            "id": "s-fmt", "severity": "low", "category": "formatting",
            "title": "Adjust resume length",
            "why": "Aim for roughly 400–800 words — too short looks thin, too long loses recruiters.",
        })
    if not out:
        out.append({
            "id": "s-ok", "severity": "low", "category": "formatting",
            "title": "You're in good shape",
            "why": "LLM-written suggestions (RAG-grounded) arrive in Phase 2.",
        })
    return out
