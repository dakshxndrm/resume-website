"""Scoring service — Phase 1 (real signals).

Upgraded from the earlier stub: skills, experience, education and projects now
come from the real parsed resume, and the semantic score blends keyword
coverage, BM25 relevance and Sentence-BERT cosine similarity of the resume text
against the job description.

Weighted formula (per docs/PROJECT_PLAN.md):
  skills 30 · experience 25 · semantic 20 · projects 10 · education 10 · formatting 5

Phase 4/5 swaps the SBERT half of the semantic scorer for the distilled JEPA
(see ml/README.md). Nothing else in this file changes when that happens.

SBERT model weights (~90MB) download on first use. `warm_semantic_model()` is
called from main.py's lifespan handler so that download and the model load happen
at boot, never inside a /score request. Set SBERT_DISABLED=1 to skip SBERT
entirely and run on the lexical signals alone.

Measured on CPU (Windows laptop, warm HuggingFace cache):
  startup model load  ~10.2 s  (one-time; includes importing torch)
  /score semantic     ~62 ms   per call, vs ~0.2 ms lexical-only
The 62 ms is two short encodes per request and dominates the scoring path, but
it is well inside a normal HTTP budget. If it ever isn't, cache embeddings by
text hash — the same JD gets scored over and over in the editor's live rescoring.
"""
from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from typing import Any

from rank_bm25 import BM25Okapi

from app.services.parsing import SKILL_VOCAB, _pretty_skill

logger = logging.getLogger(__name__)

# Same model the ml/ research track benchmarks against (see ml/baseline.py) —
# keeping them identical means ml/eval.py's verdict is about the model, not the setup.
SBERT_MODEL = os.getenv("SBERT_MODEL", "all-MiniLM-L6-v2")

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


# --------------------------------------------------------------- SBERT
# Cosine similarity between two MiniLM embeddings of real resume/JD text lands
# in roughly 0.15 (unrelated) .. 0.75 (same role, same words). Feeding raw cosine
# straight in would squash everything into the middle of the 0–100 scale, so we
# stretch that observed band across the full range. These two numbers are the
# calibration knob — retune them on real traffic, they are not laws of nature.
SBERT_FLOOR = 0.15
SBERT_CEIL = 0.75


@lru_cache(maxsize=1)
def _sbert():
    """Load the model once per process. Returns None if it is unavailable.

    lru_cache is the cache: first caller pays the load, everyone after gets the
    same object. A None result is cached too, so a broken install costs one
    failed import, not one per request.
    """
    if os.getenv("SBERT_DISABLED"):
        logger.info("SBERT_DISABLED set — semantic score using lexical signals only")
        return None
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(SBERT_MODEL)
    except Exception as exc:  # missing package, no disk space, no network on first pull
        logger.warning(
            "sentence-transformers unavailable (%s) — semantic score falling back to "
            "BM25 + keyword coverage. Install it with: pip install -r requirements.txt",
            exc,
        )
        return None


def warm_semantic_model() -> bool:
    """Force the model load at boot instead of during the first /score request.

    Called from main.py's lifespan handler. Returns whether SBERT is available, so
    startup can log which mode the process is running in.
    """
    return _sbert() is not None


def _sbert_similarity(resume_text: str, job_description: str) -> float | None:
    """Calibrated 0..1 semantic similarity, or None if SBERT isn't usable.

    Note: MiniLM reads only the first ~256 word pieces (~1200 characters) of each
    input, so a long resume is judged on its opening. That is usually the summary
    and most recent role, which is the right part to weigh.
    ponytail: chunk-and-average the resume if truncation shows up as a real problem.
    """
    model = _sbert()
    if model is None:
        return None
    try:
        vectors = model.encode([resume_text, job_description], convert_to_numpy=True)
        a, b = vectors[0], vectors[1]
        denominator = float((a @ a) ** 0.5 * (b @ b) ** 0.5)
        if denominator <= 0:
            return None
        cosine = float(a @ b) / denominator
    except Exception as exc:  # never let an embedding failure kill a score request
        logger.warning("SBERT encode failed (%s) — falling back to lexical signals", exc)
        return None

    stretched = (cosine - SBERT_FLOOR) / (SBERT_CEIL - SBERT_FLOOR)
    return min(1.0, max(0.0, stretched))


def _semantic_score(resume_text: str, job_description: str | None) -> int:
    """Real relevance of resume text to the job description.

    No JD → neutral 60 (can't compare). With a JD → three signals blended:

      keyword coverage 33% · BM25 relevance 22% · SBERT cosine 45%

    Why these weights: ATS filters match keywords *literally*, so the lexical
    signals keep the majority (55%) — a resume that never says "Kubernetes" should
    not score well on a Kubernetes job just because it says "container orchestration".
    SBERT gets the single largest share (45%) because it is the only signal that
    survives paraphrasing, which is exactly where the lexical pair scores near zero.
    The 60/40 split *within* the lexical half is the ratio this file already shipped,
    left alone deliberately.

    If SBERT is unavailable the lexical half is renormalised back to 100% — i.e.
    exactly the pre-SBERT behaviour, not a silently deflated score.
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

    lexical = 0.6 * coverage + 0.4 * bm25_norm
    semantic = _sbert_similarity(resume_text, job_description)

    blended = lexical if semantic is None else 0.55 * lexical + 0.45 * semantic
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