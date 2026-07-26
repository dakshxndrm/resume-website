"""Resume parsing service — Phase 1.

Turns an uploaded PDF/DOCX file into structured data the scorer can use:
text extraction (PyMuPDF for PDF, python-docx for DOCX) + keyword-based skill
extraction + light section detection. No spaCy yet (kept simple/free); the plan
upgrades this to spaCy NER + normalization later. See docs/PROJECT_PLAN.md.
"""
from __future__ import annotations

import io
import re
from typing import Any

import fitz  # PyMuPDF
from docx import Document

# ---------------------------------------------------------------------------
# 1. A small skills vocabulary. Extend freely — this is the "known skills" list
#    the extractor looks for in resume + job-description text.
# ---------------------------------------------------------------------------
SKILL_VOCAB: list[str] = [
    # languages
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "kotlin", "swift", "php", "ruby", "r", "sql", "html", "css", "bash",
    # frontend
    "react", "next.js", "vue", "angular", "tailwind css", "redux", "jest",
    "webpack", "vite", "accessibility",
    # backend
    "node.js", "express", "django", "flask", "fastapi", "spring boot",
    "graphql", "rest apis", "microservices",
    # data / ml
    "pandas", "numpy", "scikit-learn", "pytorch", "tensorflow", "keras",
    "opencv", "nlp", "machine learning", "deep learning", "data analysis",
    "statistics", "data visualization", "mlops",
    # db / infra
    "postgresql", "mysql", "mongodb", "redis", "sqlite", "docker",
    "kubernetes", "aws", "gcp", "azure", "ci/cd", "git", "linux",
    # soft
    "communication", "teamwork", "leadership", "problem solving", "agile",
]

# match multi-word skills first so "next.js" isn't half-matched by "js"
_SKILL_PATTERNS = sorted(SKILL_VOCAB, key=len, reverse=True)

_DEGREE_WORDS = ["b.tech", "btech", "b.e", "bachelor", "master", "m.tech",
                 "phd", "diploma", "b.sc", "m.sc", "mba", "b.com"]

_EXP_HEADINGS = ["experience", "work history", "employment", "internship"]
_PROJ_HEADINGS = ["projects", "personal projects", "academic projects"]
_EDU_HEADINGS = ["education", "academic", "qualification"]


# ---------------------------------------------------------------------------
# 2. Text extraction
# ---------------------------------------------------------------------------
def extract_text(file_bytes: bytes, filename: str) -> str:
    """Return plain text from a PDF or DOCX file (empty string if unreadable)."""
    name = (filename or "").lower()
    try:
        if name.endswith(".pdf"):
            return _pdf_text(file_bytes)
        if name.endswith(".docx"):
            return _docx_text(file_bytes)
        if name.endswith(".doc"):
            # legacy .doc not supported by python-docx; ask user for PDF/DOCX
            return ""
    except Exception:
        return ""
    return ""


def _pdf_text(file_bytes: bytes) -> str:
    text_parts: list[str] = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text("text"))
    return "\n".join(text_parts)


def _docx_text(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs)


# ---------------------------------------------------------------------------
# 3. Field extraction
# ---------------------------------------------------------------------------
def extract_skills(text: str) -> list[str]:
    """Find known skills present in the text (case-insensitive, whole-word)."""
    low = text.lower()
    found: list[str] = []
    for skill in _SKILL_PATTERNS:
        pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
        if re.search(pattern, low):
            found.append(skill)
    # return in a stable, de-duplicated, title-ish form
    seen: set[str] = set()
    out: list[str] = []
    for s in found:
        if s not in seen:
            seen.add(s)
            out.append(_pretty_skill(s))
    return out


def _pretty_skill(s: str) -> str:
    special = {
        "next.js": "Next.js", "node.js": "Node.js", "c++": "C++", "c#": "C#",
        "rest apis": "REST APIs", "ci/cd": "CI/CD", "html": "HTML", "css": "CSS",
        "sql": "SQL", "aws": "AWS", "gcp": "GCP", "nlp": "NLP", "mlops": "MLOps",
        "tailwind css": "Tailwind CSS", "r": "R",
        # .title() mangles these — they appear verbatim in job descriptions
        "javascript": "JavaScript", "typescript": "TypeScript", "php": "PHP",
        "fastapi": "FastAPI", "graphql": "GraphQL", "numpy": "NumPy",
        "scikit-learn": "scikit-learn", "pytorch": "PyTorch",
        "tensorflow": "TensorFlow", "opencv": "OpenCV",
        "postgresql": "PostgreSQL", "mysql": "MySQL", "mongodb": "MongoDB",
        "sqlite": "SQLite",
    }
    return special.get(s, s.title())


def _count_entries(text: str, headings: list[str], item_words: list[str] | None = None) -> int:
    """Very light heuristic: how many entries a section likely has.

    Counts date-range lines (e.g. '2021 - 2023', 'Jan 2020 - Present') inside the
    text, falling back to counting given keyword hits. Good enough as a real signal
    until proper section parsing (spaCy) lands.
    """
    date_ranges = re.findall(
        r"(?:19|20)\d{2}\s*[-–—to]+\s*(?:(?:19|20)\d{2}|present|current|now)",
        text, flags=re.I,
    )
    if date_ranges:
        return len(date_ranges)
    if item_words:
        return sum(1 for w in item_words if re.search(re.escape(w), text, flags=re.I))
    # last resort: is any heading present at all?
    return 1 if any(h in text.lower() for h in headings) else 0


def parse_resume(file_bytes: bytes, filename: str) -> dict[str, Any]:
    """Turn an uploaded file into the structured dict the scorer expects."""
    text = extract_text(file_bytes, filename)

    skills = extract_skills(text)
    exp_count = _count_entries(text, _EXP_HEADINGS)
    edu_count = _count_entries(text, _EDU_HEADINGS, item_words=_DEGREE_WORDS)
    proj_count = max(
        _count_entries(text, _PROJ_HEADINGS),
        len(re.findall(r"\bproject\b", text, flags=re.I)) // 2,
    )

    # scorer counts list length, so build placeholder-entry lists of the right size
    return {
        "raw_text": text,
        "skills": skills,
        "work": [{"i": i} for i in range(exp_count)],
        "education": [{"i": i} for i in range(edu_count)],
        "projects": [{"i": i} for i in range(proj_count)],
        "word_count": len(text.split()),
    }
