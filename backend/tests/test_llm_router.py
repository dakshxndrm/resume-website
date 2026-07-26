"""LLM router: every failure path must return None, and the key must never leak.

requests.post is always monkeypatched here — a test that reaches the real Groq
API is a bug in the test, so the default fake raises if it is called unexpectedly.
"""
import json
import logging

import pytest

from app.services import llm_router
from app.services.llm_router import generate_suggestions

FAKE_KEY = "gsk_TOTALLY_FAKE_KEY_abc123"
ITEM_KEYS = {"id", "severity", "category", "title", "why"}
REPORT = {"categories": [{"key": "skills", "score": 40}], "missingSkills": ["Kubernetes"]}


class FakeResponse:
    def __init__(self, status_code=200, payload=None, content=None, text=""):
        self.status_code = status_code
        self.text = text
        self._payload = payload
        self._content = content

    def json(self):
        if self._payload is not None:
            return self._payload
        return {"choices": [{"message": {"content": self._content}}]}


class Recorder:
    """Stand-in for requests.post that records calls and returns a canned response."""

    def __init__(self, response=None, exc=None):
        self.response, self.exc, self.calls = response, exc, []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.exc:
            raise self.exc
        return self.response


@pytest.fixture
def post(monkeypatch):
    """Patched requests.post. Tests set `post.response` / `post.exc`."""
    rec = Recorder(response=FakeResponse(content=json.dumps({"suggestions": []})))
    monkeypatch.setattr(llm_router.requests, "post", rec)
    return rec


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setattr(llm_router.settings, "groq_api_key", FAKE_KEY)
    monkeypatch.setattr(llm_router.settings, "groq_model", "test-model")


def suggestions(*items):
    return FakeResponse(content=json.dumps({"suggestions": list(items)}))


GOOD_ITEM = {"severity": "high", "category": "experience",
             "title": "Quantify your impact", "why": "None of your bullets carry a number."}


# ---------------------------------------------------------------- disabled
def test_no_api_key_returns_none_without_calling_out(post):
    """The autouse fixture blanks the key, so this is the default state."""
    assert generate_suggestions("resume text", None, REPORT) is None
    assert post.calls == [], "must not touch the network when the feature is off"


def test_whitespace_only_api_key_is_treated_as_absent(post, monkeypatch):
    monkeypatch.setattr(llm_router.settings, "groq_api_key", "   ")
    assert generate_suggestions("resume text", None, REPORT) is None
    assert post.calls == []


# ---------------------------------------------------------------- happy path
def test_valid_response_is_normalized(post, with_key):
    post.response = suggestions(GOOD_ITEM, {**GOOD_ITEM, "title": "Add Kubernetes"})
    out = generate_suggestions("resume text", "job description", REPORT)

    assert isinstance(out, list) and len(out) == 2
    for item in out:
        assert set(item) == ITEM_KEYS
        assert item["severity"] in {"high", "medium", "low"}
    assert len(post.calls) == 1


def test_bare_list_response_is_accepted(post, with_key):
    post.response = FakeResponse(content=json.dumps([GOOD_ITEM]))
    out = generate_suggestions("resume", None, REPORT)
    assert out and set(out[0]) == ITEM_KEYS


# ---------------------------------------------------------------- coercion
def test_bad_severity_and_category_are_coerced(post, with_key):
    post.response = suggestions({**GOOD_ITEM, "severity": "CRITICAL", "category": "vibes"})
    out = generate_suggestions("resume", None, REPORT)
    assert out[0]["severity"] == "medium"
    assert out[0]["category"] == "skills"


def test_items_missing_title_or_why_are_dropped(post, with_key):
    post.response = suggestions(
        {"severity": "high", "category": "skills", "why": "no title here"},
        {"severity": "high", "category": "skills", "title": "no why here"},
        GOOD_ITEM,
    )
    out = generate_suggestions("resume", None, REPORT)
    assert len(out) == 1 and out[0]["title"] == GOOD_ITEM["title"]


def test_all_items_unusable_returns_none(post, with_key):
    post.response = suggestions({"severity": "high"}, "not even a dict")
    assert generate_suggestions("resume", None, REPORT) is None


# ---------------------------------------------------------------- failure paths
def test_rate_limited_returns_none(post, with_key):
    post.response = FakeResponse(status_code=429, text='{"error":{"message":"rate limit reached"}}')
    assert generate_suggestions("resume", None, REPORT) is None


def test_unparseable_content_returns_none(post, with_key):
    post.response = FakeResponse(content="Sure! Here are your suggestions: <not json>")
    assert generate_suggestions("resume", None, REPORT) is None


def test_unexpected_body_shape_returns_none(post, with_key):
    post.response = FakeResponse(payload={"nope": "no choices key"})
    assert generate_suggestions("resume", None, REPORT) is None


def test_network_exception_returns_none(post, with_key):
    post.exc = ConnectionError("network is down")
    assert generate_suggestions("resume", None, REPORT) is None


# ---------------------------------------------------------------- secret hygiene
def test_api_key_never_appears_in_logs(post, with_key, caplog):
    """Walk every failure path with the key set and scan all captured log output."""
    caplog.set_level(logging.DEBUG)

    for response, exc in [
        (FakeResponse(status_code=401, text='{"error":"Invalid API Key"}'), None),
        (FakeResponse(status_code=429, text='{"error":"rate limit"}'), None),
        (FakeResponse(content="not json"), None),
        (suggestions({"severity": "high"}), None),
        (None, ConnectionError("network is down")),
    ]:
        post.response, post.exc = response, exc
        assert generate_suggestions("resume", "jd", REPORT) is None

    assert caplog.records, "expected these paths to log something"
    for record in caplog.records:
        assert FAKE_KEY not in record.getMessage()
        assert FAKE_KEY not in str(record.args)


def test_api_key_is_sent_only_in_the_auth_header(post, with_key):
    post.response = suggestions(GOOD_ITEM)
    generate_suggestions("resume", "jd", REPORT)

    _, kwargs = post.calls[0]
    assert kwargs["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert FAKE_KEY not in json.dumps(kwargs["json"])
