"""Scoring service — STUB.

Phase 1 replaces this with: parsing (PyMuPDF/pdfplumber + spaCy NER) →
BM25 + Sentence-BERT → weighted formula (skills 30 / experience 25 / semantic 20 /
projects 10 / education 10 / formatting 5). Phase 5 swaps semantic scorer to JEPA.
See docs/PROJECT_PLAN.md.
"""
from typing import Any

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


def score_resume(resume: dict[str, Any], job_description: str | None = None) -> dict[str, Any]:
    """Placeholder heuristic so the full product loop works end-to-end today."""
    skills = resume.get("skills", [])
    work = resume.get("work", [])
    education = resume.get("education", [])
    projects = resume.get("projects", [])

    cat_scores = {
        "skills": min(100, 30 + len(skills) * 9),
        "experience": min(100, 30 + len(work) * 25),
        "semantic": 60,  # real semantic scoring lands in Phase 1 (SBERT) / Phase 5 (JEPA)
        "projects": min(100, 20 + len(projects) * 30),
        "education": min(100, 40 + len(education) * 30),
        "formatting": 80,
    }
    total = round(sum(cat_scores[k] * w for k, w in WEIGHTS.items()))

    return {
        "total": total,
        "verdict": _verdict(total),
        "categories": [
            {"key": k, "label": _LABELS[k], "score": cat_scores[k], "weight": w}
            for k, w in WEIGHTS.items()
        ],
        "suggestions": _stub_suggestions(cat_scores),
        "missingSkills": [],
    }


def _verdict(total: int) -> str:
    if total >= 80:
        return "Strong resume — a few refinements left"
    if total >= 60:
        return "Good foundation — several fixes found"
    return "Needs work — but every issue below is fixable"


def _stub_suggestions(cat_scores: dict[str, int]) -> list[dict]:
    out = []
    if cat_scores["skills"] < 70:
        out.append({"id": "s1", "severity": "high", "category": "skills",
                    "title": "Add more role-relevant skills",
                    "why": "Your skills section is thin — ATS keyword matching weighs it heavily."})
    if cat_scores["experience"] < 70:
        out.append({"id": "s2", "severity": "high", "category": "experience",
                    "title": "Expand your work experience entries",
                    "why": "Add measurable achievements to each role — numbers get noticed."})
    if not out:
        out.append({"id": "s0", "severity": "low", "category": "formatting",
                    "title": "You're in good shape",
                    "why": "Full suggestion engine (RAG + LLM) arrives in Phase 2 — check back."})
    return out
