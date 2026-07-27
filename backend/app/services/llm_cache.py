"""Suggestion cache and per-caller daily rate limiting.

Both exist for the same reason: the Groq free tier is a shared daily quota across
every user of this site, so one enthusiastic user in the live editor can exhaust
it for everyone. The cache removes repeat calls; the limiter caps the rest.

Everything here is best-effort. A cache miss, a cache write failure, a counter
that cannot be read — none of them may break a score request. Every function
either returns a safe default or is wrapped by its caller.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import LlmUsage, SuggestionCache

log = logging.getLogger(__name__)

_WS = re.compile(r"\s+")


def _utc_naive() -> datetime:
    """Naive UTC, matching the naive DateTime columns in models.py."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize(text: str | None) -> str:
    """Lowercase and collapse whitespace.

    This is what makes trivial edits still hit the cache: re-indenting a bullet,
    fixing capitalisation, or adding a trailing newline produces the same key.
    Deliberately NOT more aggressive than that — dropping punctuation or
    stemming would make genuinely different resumes collide, and the user would
    get advice written about somebody else's document.
    """
    return _WS.sub(" ", (text or "").strip().lower())


def cache_key(resume_text: str, job_description: str | None) -> str:
    """sha256 of the normalized pair. The JD is part of the key because the same
    resume against a different job deserves different advice."""
    joined = f"{normalize(resume_text)}\x00{normalize(job_description)}"
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


# TTL: how long a cached suggestion set stays valid.
# 30 days by default. Suggestions describe a resume against a job posting, and
# neither changes underneath us — the reason to expire at all is that the prompt,
# the model, or the scoring weights change, and stale advice would then contradict
# a fresh score. Configurable via SUGGESTION_CACHE_TTL_HOURS.
def ttl_cutoff() -> datetime:
    hours = max(1, int(settings.suggestion_cache_ttl_hours))
    return _utc_naive() - timedelta(hours=hours)


def get_cached(db: Session, key: str) -> list[dict] | None:
    """Fresh cached suggestions for this key, or None. Never raises."""
    try:
        row = db.query(SuggestionCache).filter_by(cache_key=key).first()
        if row is None:
            return None
        if row.created_at is not None and row.created_at < ttl_cutoff():
            return None  # expired; left in place for the sweeper, not read
        return row.suggestions or None
    except Exception as exc:
        log.warning("suggestion cache read failed (%s) - treating as a miss", exc)
        return None


def put_cached(db: Session, key: str, suggestions: list[dict], user_id: str | None) -> bool:
    """Store suggestions. Returns whether the write landed. Never raises."""
    try:
        existing = db.query(SuggestionCache).filter_by(cache_key=key).first()
        if existing:
            existing.suggestions = suggestions
            existing.created_at = _utc_naive()
            existing.user_id = existing.user_id or user_id
        else:
            db.add(SuggestionCache(cache_key=key, suggestions=suggestions, user_id=user_id))
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        log.warning("suggestion cache write failed (%s) - continuing without it", exc)
        return False


# --------------------------------------------------------------- rate limiting
def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def subject_for(user_id: str | None, client_ip: str | None) -> str:
    """Who is being counted. Signed-in users get their own bucket; everyone else
    shares one keyed by IP, which is coarse (offices and mobile carriers NAT) and
    is why the anonymous cap is deliberately generous per-person but small."""
    if user_id:
        return f"user:{user_id}"
    return f"ip:{client_ip or 'unknown'}"


def daily_limit(user_id: str | None) -> int:
    return (settings.llm_daily_limit_user if user_id
            else settings.llm_daily_limit_anon)


def usage_today(db: Session, subject: str) -> int:
    try:
        row = db.query(LlmUsage).filter_by(subject=subject, day=_today()).first()
        return row.count if row else 0
    except Exception as exc:
        log.warning("rate-limit read failed (%s) - allowing the call", exc)
        return 0  # fail open: a broken counter must not block scoring


def within_limit(db: Session, user_id: str | None, client_ip: str | None) -> bool:
    limit = daily_limit(user_id)
    if limit <= 0:
        return False  # 0 is a valid way to switch the LLM off entirely
    return usage_today(db, subject_for(user_id, client_ip)) < limit


def record_call(db: Session, user_id: str | None, client_ip: str | None) -> None:
    """Count one LLM call against today's bucket. Never raises.

    Counted on attempt, not on success: a failed or rate-limited Groq call still
    consumed quota, and counting only successes would let a failing key retry
    forever.
    """
    subject = subject_for(user_id, client_ip)
    try:
        row = db.query(LlmUsage).filter_by(subject=subject, day=_today()).first()
        if row:
            row.count += 1
        else:
            db.add(LlmUsage(subject=subject, day=_today(), count=1))
        db.commit()
    except Exception as exc:
        db.rollback()
        log.warning("rate-limit write failed (%s) - call not counted", exc)


def purge_for_user(db: Session, user_id: str) -> int:
    """Delete this user's cached suggestions. Called by DELETE /users/me.

    Cached rows hold feedback written about a real resume, so they are user data
    and must go with everything else.
    """
    return db.query(SuggestionCache).filter(
        SuggestionCache.user_id == user_id
    ).delete(synchronize_session=False)
