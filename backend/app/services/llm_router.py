"""LLM suggestions via Groq (OpenAI-compatible chat completions API).

Fail-safe by design: EVERY error path returns None, so the caller simply keeps
the existing rule-based suggestions and the app never breaks. The API key is
never logged or returned.
"""
from __future__ import annotations

import json
import logging
import uuid

import requests

from app.core.config import settings

# Groq speaks the OpenAI chat-completions dialect at this URL.
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

log = logging.getLogger(__name__)

# Groq free tier is tokens-per-minute limited — keep the prompt small.
_MAX_RESUME_CHARS = 4000
_MAX_JD_CHARS = 2000
_MAX_ITEMS = 6

# The frontend only renders these values, so anything else gets coerced.
_SEVERITIES = {"high", "medium", "low"}
_CATEGORIES = {"skills", "experience", "semantic", "projects", "education", "formatting"}

_SYSTEM_PROMPT = (
    "You are an expert technical resume reviewer. "
    "You reply with valid json only - no markdown fences, no commentary."
)


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _user_prompt(resume_text: str, job_description: str | None, report: dict) -> str:
    """Build the single user message. Truncated to stay inside the free tier."""
    scores = ", ".join(
        f"{c.get('key')}={c.get('score')}" for c in report.get("categories") or []
    ) or "unknown"
    missing = ", ".join(report.get("missingSkills") or []) or "none detected"
    jd = (job_description or "").strip()[:_MAX_JD_CHARS] or "(no job description given)"
    resume = (resume_text or "").strip()[:_MAX_RESUME_CHARS] or "(resume text unavailable)"

    return f"""Review this resume and return improvement suggestions as json.

Category scores (0-100): {scores}
Missing skills detected: {missing}

JOB DESCRIPTION:
{jd}

RESUME:
{resume}

Return exactly this json object shape:
{{"suggestions": [{{"severity": "high", "category": "skills", "title": "...", "why": "..."}}]}}

Rules:
- 3 to 6 items, ordered highest severity first.
- "severity" must be one of: high, medium, low.
- "category" must be one of: skills, experience, semantic, projects, education, formatting.
- "title": imperative, 8 words maximum.
- "why": 1-2 concrete sentences referencing a real gap you can see above.
- Never invent experience, employers, or skills the candidate does not have.
"""


def _clean(items: list) -> list[dict]:
    """Coerce raw model output into the exact shape the frontend renders."""
    out: list[dict] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()
        why = str(raw.get("why") or "").strip()
        if not title or not why:
            continue  # unusable item — drop it rather than render a blank card

        severity = str(raw.get("severity") or "").strip().lower()
        category = str(raw.get("category") or "").strip().lower()
        out.append({
            "id": str(raw.get("id") or f"ai-{uuid.uuid4().hex[:8]}"),
            "severity": severity if severity in _SEVERITIES else "medium",
            "category": category if category in _CATEGORIES else "skills",
            "title": title[:80],
            "why": why[:280],
        })
        if len(out) >= _MAX_ITEMS:
            break
    return out


def generate_suggestions(
    resume_text: str, job_description: str | None, report: dict
) -> list[dict] | None:
    """Return LLM suggestions, or None if unavailable for ANY reason."""
    api_key = (settings.groq_api_key or "").strip()
    if not api_key:
        return None  # feature simply off — not an error, don't log

    model = (settings.groq_model or "llama-3.3-70b-versatile").strip()
    try:
        resp = requests.post(
            GROQ_URL,
            headers=_headers(api_key),
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _user_prompt(resume_text, job_description, report)},
                ],
                "temperature": 0.4,
                "max_tokens": 900,
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        if resp.status_code != 200:
            # 401 bad key, 404 wrong model name, 429 quota — all just fall back.
            log.warning("Groq %s returned HTTP %s: %s", model, resp.status_code, resp.text[:200])
            return None

        content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        # response_format=json_object means we expect an object, but accept a
        # bare list too in case the model ignores that.
        items = data if isinstance(data, list) else data.get("suggestions") or []
        cleaned = _clean(items) if isinstance(items, list) else []
        if not cleaned:
            log.warning("Groq %s returned no usable suggestions", model)
            return None
        return cleaned
    except Exception as exc:  # network, timeout, bad json, unexpected shape
        log.warning("Groq %s suggestion call failed: %s: %s", model, type(exc).__name__, exc)
        return None


def ping() -> str:
    """Cheapest possible call. Returns "" on success, or a short error message."""
    api_key = (settings.groq_api_key or "").strip()
    model = (settings.groq_model or "llama-3.3-70b-versatile").strip()
    try:
        resp = requests.post(
            GROQ_URL,
            headers=_headers(api_key),
            json={
                "model": model,
                "messages": [{"role": "user", "content": "reply with the word ok"}],
                "max_tokens": 5,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return f"HTTP {resp.status_code}: {resp.text[:150]}"
        resp.json()["choices"][0]["message"]["content"]  # shape check
        return ""
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
