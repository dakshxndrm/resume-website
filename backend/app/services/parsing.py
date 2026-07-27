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

# Heading text that starts each section, normalised (lowercase, punctuation
# stripped). A line is a heading only if it matches one of these *exactly* — a
# sentence that merely mentions "experience" is body text, not a new section.
_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "experience": (
        "experience", "work experience", "professional experience", "work history",
        "employment", "employment history", "additional experience", "internship",
        "internships", "career history",
    ),
    "education": (
        "education", "academics", "academic background", "qualification",
        "qualifications", "educational qualifications",
    ),
    "projects": (
        "projects", "personal projects", "academic projects", "side projects",
        "selected projects",
    ),
    "skills": ("skills", "technical skills", "core competencies", "competencies"),
    "summary": ("summary", "objective", "profile", "about", "about me"),
}

_DATE_RANGE = re.compile(
    r"(?:19|20)\d{2}\s*[-–—to]+\s*(?:(?:19|20)\d{2}|present|current|now)",
    flags=re.I,
)
_DEGREE_RE = re.compile(
    r"(?<![a-z])(?:" + "|".join(re.escape(w) for w in _DEGREE_WORDS) + r")(?![a-z])",
    flags=re.I,
)


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


def _heading_of(line: str) -> str | None:
    """Which section this line opens, or None if it is body text."""
    norm = " ".join(re.sub(r"[^a-z ]+", " ", line.lower()).split())
    if not norm or len(norm.split()) > 5:
        return None
    for name, aliases in _SECTION_ALIASES.items():
        if norm in aliases:
            return name
    return None


def split_sections(text: str) -> dict[str, str]:
    """Split a resume into {section name: body text}.

    Text before the first heading lands under "_preamble". A heading that appears
    twice (EXPERIENCE ... ADDITIONAL EXPERIENCE) merges into one section.

    This exists because counting date ranges across the whole document made work,
    education and projects return the *same* number every time — one signal driving
    45% of the score. Counting inside a section keeps them independent.
    """
    sections: dict[str, list[str]] = {}
    current, buf = "_preamble", []
    for line in (text or "").splitlines():
        heading = _heading_of(line)
        if heading:
            sections.setdefault(current, []).extend(buf)
            current, buf = heading, []
            continue
        buf.append(line)
    sections.setdefault(current, []).extend(buf)
    return {name: "\n".join(lines) for name, lines in sections.items()}


def _count_section_entries(section: str | None) -> int:
    """How many entries a *single section* holds. 0 when the section is absent.

    Date ranges are the primary signal; a section with none (a resume that lists no
    dates, or a projects list) falls back to blank-line-separated blocks. There is
    deliberately no document-wide fallback — that was the bug.
    """
    if not section or not section.strip():
        return 0
    dates = len(_DATE_RANGE.findall(section))
    if dates:
        return dates
    return len([b for b in re.split(r"\n\s*\n", section) if b.strip()])


def parse_resume(file_bytes: bytes, filename: str) -> dict[str, Any]:
    """Turn an uploaded file into the structured dict the scorer expects."""
    text = extract_text(file_bytes, filename)
    sections = split_sections(text)

    skills = extract_skills(text)
    exp_count = _count_section_entries(sections.get("experience"))
    # education is degree-driven: "B.Tech ... M.Sc ..." is two entries even when
    # neither carries a date range.
    edu_section = sections.get("education")
    edu_count = (len(_DEGREE_RE.findall(edu_section)) if edu_section else 0) or \
        _count_section_entries(edu_section)
    proj_count = _count_section_entries(sections.get("projects"))

    # scorer counts list length, so build placeholder-entry lists of the right size
    return {
        "raw_text": text,
        "skills": skills,
        "work": [{"i": i} for i in range(exp_count)],
        "education": [{"i": i} for i in range(edu_count)],
        "projects": [{"i": i} for i in range(proj_count)],
        "word_count": len(text.split()),
    }
