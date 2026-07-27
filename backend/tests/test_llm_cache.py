"""Suggestion cache + per-caller daily rate limiting.

Groq is never reached: every test either has no API key (conftest blanks it) or
replaces requests.post with a fake that counts calls. If a test in here makes a
real HTTP request, that is the bug it is meant to catch.
"""
import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user, get_optional_user
from app.core.config import settings
from app.core.db import get_db
from app.main import app
from app.models.models import LlmUsage, SuggestionCache, User
from app.services import llm_cache, llm_router

CLAIMS = {"uid": "cache-uid", "email": "cache@example.com", "name": "Cache User"}

RESUME = {"skills": ["Python"], "work": [{}], "education": [{}], "projects": [{}],
          "raw_text": "Backend engineer building REST APIs in Python with FastAPI.",
          "word_count": 10}
JD = "Backend Engineer. Python, FastAPI and PostgreSQL."

AI_SUGGESTIONS = [
    {"id": "ai-1", "severity": "high", "category": "skills",
     "title": "Add PostgreSQL to your skills", "why": "The job asks for it explicitly."},
]


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = str(self._payload)

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _reset_llm_state():
    """The 429 cooldown is process-global; leaking it across tests would silently
    disable the LLM for everything that runs after."""
    llm_router.reset_cooldown()
    yield
    llm_router.reset_cooldown()


@pytest.fixture
def groq(monkeypatch):
    """Groq enabled, answering successfully, counting how many times it was called."""
    monkeypatch.setattr(settings, "groq_api_key", "test-key", raising=False)
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        return FakeResponse(200, {"choices": [{"message": {
            "content": '{"suggestions": [{"severity": "high", "category": "skills", '
                       '"title": "Add PostgreSQL to your skills", '
                       '"why": "The job asks for it explicitly."}]}'}}]})

    monkeypatch.setattr(llm_router.requests, "post", fake_post)
    return calls


@pytest.fixture
def user(db_session):
    row = User(firebase_uid=CLAIMS["uid"], email=CLAIMS["email"], name=CLAIMS["name"])
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


@pytest.fixture
def authed(db_session, user):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: CLAIMS
    app.dependency_overrides[get_optional_user] = lambda: CLAIMS
    yield TestClient(app)
    app.dependency_overrides.clear()


def post_score(client, resume=None, jd=JD):
    return client.post("/score", json={"resume": resume or RESUME, "job_description": jd})


# ---------------------------------------------------------------- key derivation
def test_key_ignores_whitespace_and_case():
    a = llm_cache.cache_key("Backend   Engineer\n\nPython", "FastAPI  role")
    b = llm_cache.cache_key("  backend engineer python  ", "fastapi role")
    assert a == b


def test_key_separates_different_job_descriptions():
    """Same resume, different job = different advice. Must not collide."""
    a = llm_cache.cache_key("same resume text", "Backend Engineer")
    b = llm_cache.cache_key("same resume text", "Frontend Engineer")
    assert a != b


def test_key_separates_different_resumes():
    assert (llm_cache.cache_key("resume one", JD)
            != llm_cache.cache_key("resume two", JD))


# ---------------------------------------------------------------- cache
def test_second_identical_request_hits_cache_and_makes_no_http_call(authed, groq):
    first = post_score(authed)
    assert first.status_code == 200
    assert first.json()["suggestionsSource"] == "ai"
    assert len(groq) == 1, "first request should call Groq exactly once"

    second = post_score(authed)
    assert second.status_code == 200
    assert second.json()["suggestionsSource"] == "cache"
    assert len(groq) == 1, "second request must not call Groq at all"
    assert second.json()["suggestions"] == first.json()["suggestions"]


def test_trivial_edits_still_hit_the_cache(authed, groq):
    """The live-editor case: whitespace and capitalisation churn must not re-bill."""
    post_score(authed)
    assert len(groq) == 1

    noisy = {**RESUME, "raw_text": "  BACKEND   Engineer building REST APIs\nin PYTHON "
                                   "with FastAPI.  "}
    # same normalized text -> same key. (raw_text is what feeds the prompt.)
    assert (llm_cache.cache_key(RESUME["raw_text"], JD)
            == llm_cache.cache_key(noisy["raw_text"], JD))


def test_a_different_job_description_misses_the_cache(authed, groq):
    post_score(authed)
    post_score(authed, jd="Frontend Engineer. React and TypeScript.")
    assert len(groq) == 2, "different JD is different advice - must call again"


def test_expired_entries_are_not_served(authed, groq, db_session, monkeypatch):
    post_score(authed)
    assert len(groq) == 1

    # push every cached row past the TTL
    monkeypatch.setattr(settings, "suggestion_cache_ttl_hours", 1, raising=False)
    for row in db_session.query(SuggestionCache).all():
        row.created_at = llm_cache.ttl_cutoff().replace(year=2000)
    db_session.commit()

    assert post_score(authed).json()["suggestionsSource"] == "ai"
    assert len(groq) == 2, "expired entry should have been refetched"


def test_cache_failure_does_not_break_scoring(authed, groq, monkeypatch):
    """A broken cache is a cache miss, never a 500."""
    def explode(*_a, **_kw):
        raise RuntimeError("cache table is on fire")

    monkeypatch.setattr(llm_cache, "get_cached", explode)
    monkeypatch.setattr(llm_cache, "put_cached", explode)

    r = post_score(authed)
    assert r.status_code == 200
    assert r.json()["total"] > 0
    assert r.json()["suggestionsSource"] in {"ai", "rules"}


def test_cache_write_failure_still_returns_ai_suggestions(authed, groq, monkeypatch):
    monkeypatch.setattr(llm_cache, "put_cached", lambda *a, **kw: False)
    r = post_score(authed)
    assert r.json()["suggestionsSource"] == "ai"
    assert r.json()["suggestions"][0]["title"] == "Add PostgreSQL to your skills"


# ---------------------------------------------------------------- rate limiting
def test_rate_limit_exceeded_returns_200_with_rule_based_suggestions(
        authed, groq, db_session, user, monkeypatch):
    monkeypatch.setattr(settings, "llm_daily_limit_user", 2, raising=False)

    # burn the allowance on distinct resumes so the cache cannot absorb them
    for i in range(2):
        post_score(authed, resume={**RESUME, "raw_text": f"Distinct resume text {i}. "
                                                         "Backend engineer with Python."})
    assert len(groq) == 2

    r = post_score(authed, resume={**RESUME, "raw_text": "Yet another distinct resume, "
                                                        "Python backend engineer."})
    assert r.status_code == 200, "over the cap must never be an error"
    assert r.json()["suggestionsSource"] == "rules"
    assert r.json()["total"] > 0 and r.json()["suggestions"], "still a full report"
    assert len(groq) == 2, "no Groq call once the cap is hit"


def test_cache_hits_do_not_consume_the_rate_limit(authed, groq, db_session, monkeypatch):
    """Otherwise the cache would save money but not headroom."""
    monkeypatch.setattr(settings, "llm_daily_limit_user", 5, raising=False)
    post_score(authed)
    for _ in range(4):
        assert post_score(authed).json()["suggestionsSource"] == "cache"

    row = db_session.query(LlmUsage).one()
    assert row.count == 1, f"cache hits were counted against the cap: {row.count}"


def test_anonymous_callers_get_the_lower_cap(client, groq, monkeypatch):
    monkeypatch.setattr(settings, "llm_daily_limit_anon", 1, raising=False)

    first = client.post("/score", json={"resume": RESUME, "job_description": JD})
    assert first.json()["suggestionsSource"] == "ai"

    second = client.post("/score", json={
        "resume": {**RESUME, "raw_text": "Different anonymous resume text about Python."},
        "job_description": JD})
    assert second.status_code == 200
    assert second.json()["suggestionsSource"] == "rules"
    assert len(groq) == 1


def test_limit_of_zero_disables_the_llm(authed, groq, monkeypatch):
    monkeypatch.setattr(settings, "llm_daily_limit_user", 0, raising=False)
    assert post_score(authed).json()["suggestionsSource"] == "rules"
    assert groq == []


def test_broken_rate_limit_counter_fails_open(authed, groq, monkeypatch):
    """A scoring request must not be blocked because a counter query broke."""
    monkeypatch.setattr(llm_cache, "usage_today",
                        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("db down")))
    r = post_score(authed)
    assert r.status_code == 200
    assert r.json()["total"] > 0


# ---------------------------------------------------------------- Groq 429
def test_groq_429_falls_back_to_rules_and_starts_a_cooldown(authed, monkeypatch):
    calls = []

    def rate_limited(url, **kwargs):
        calls.append(url)
        return FakeResponse(429, {"error": "rate limit"}, {"Retry-After": "30"})

    monkeypatch.setattr(settings, "groq_api_key", "test-key", raising=False)
    monkeypatch.setattr(llm_router.requests, "post", rate_limited)

    r = post_score(authed)
    assert r.status_code == 200
    assert r.json()["suggestionsSource"] == "rules"
    assert llm_router.is_cooling_down()

    # while cooling down, no further round trips
    post_score(authed, resume={**RESUME, "raw_text": "Another resume, Python engineer."})
    assert len(calls) == 1, "cooldown should have skipped the second HTTP call"


def test_cooldown_respects_a_malformed_retry_after(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "test-key", raising=False)
    monkeypatch.setattr(llm_router.requests, "post",
                        lambda url, **kw: FakeResponse(429, {}, {"Retry-After": "Wed, 21 Oct"}))
    assert llm_router.generate_suggestions("text", JD, {"categories": []}) is None
    assert llm_router.is_cooling_down(), "an unparseable header must not skip the cooldown"


# ---------------------------------------------------------------- deletion
def test_delete_me_removes_this_users_cached_rows(authed, groq, db_session, user):
    post_score(authed)
    assert db_session.query(SuggestionCache).count() == 1

    other = SuggestionCache(cache_key="someone-elses-key", suggestions=AI_SUGGESTIONS,
                            user_id=None)
    db_session.add(other)
    db_session.commit()

    r = authed.delete("/users/me")
    assert r.status_code == 200
    assert r.json()["deleted"]["cachedSuggestions"] == 1

    db_session.expire_all()
    remaining = db_session.query(SuggestionCache).all()
    assert len(remaining) == 1 and remaining[0].cache_key == "someone-elses-key", (
        "deletion should take this user's rows and only this user's")


def test_cached_rows_are_attributed_to_the_signed_in_user(authed, groq, db_session, user):
    post_score(authed)
    row = db_session.query(SuggestionCache).one()
    assert row.user_id == user.id, "unattributed rows would survive DELETE /users/me"
