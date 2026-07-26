"""HTTP layer, driven through TestClient with get_db pointed at in-memory SQLite.

Nothing here reaches Neon, Firebase or Groq.
"""
import pytest
from fastapi.testclient import TestClient

from app.core import auth
from app.core.db import get_db
from app.main import app

WEIGHT_KEYS = {"skills", "experience", "semantic", "projects", "education", "formatting"}


def upload(client, data: bytes, name="resume.pdf", **form):
    return client.post(
        "/score/upload",
        files={"file": (name, data, "application/pdf")},
        data=form,
    )


# ---------------------------------------------------------------- upload
def test_upload_pdf_returns_full_report(client, sample_pdf_bytes):
    r = upload(client, sample_pdf_bytes)
    assert r.status_code == 200, r.text

    body = r.json()
    for key in ("total", "verdict", "categories", "suggestions", "missingSkills", "report_id"):
        assert key in body
    assert body["suggestionsSource"] == "rules", "no GROQ_API_KEY — must fall back to rules"
    assert {c["key"] for c in body["categories"]} == WEIGHT_KEYS
    assert 0 <= body["total"] <= 100
    assert body["suggestions"]


def test_upload_garbage_is_422_not_500(client):
    r = upload(client, b"definitely not a pdf at all")
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert isinstance(detail, str) and "text" in detail.lower()


def test_upload_docx(client, sample_docx_bytes):
    r = client.post(
        "/score/upload",
        files={"file": ("resume.docx", sample_docx_bytes,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["total"] > 0


def test_upload_with_job_description_populates_missing_skills(client, sample_pdf_bytes):
    r = upload(client, sample_pdf_bytes,
               job_description="Platform role. Must know Kubernetes, Rust and GraphQL.")
    assert r.status_code == 200, r.text

    body = r.json()
    missing = {s.lower() for s in body["missingSkills"]}
    assert {"kubernetes", "rust", "graphql"} <= missing
    assert "python" not in missing, "the resume has Python — it isn't missing"
    assert body["jobTitle"]


def test_upload_report_is_persisted_and_retrievable(client, sample_pdf_bytes):
    report_id = upload(client, sample_pdf_bytes).json()["report_id"]

    r = client.get(f"/report/{report_id}")
    assert r.status_code == 200
    assert r.json()["id"] == report_id


def test_upload_survives_a_database_failure(sample_pdf_bytes):
    """Persistence is best-effort: a dead DB must not cost the user their report."""
    class DeadSession:
        def add(self, _):
            raise RuntimeError("connection to Neon lost")

        def rollback(self):
            pass

    app.dependency_overrides[get_db] = lambda: DeadSession()
    try:
        r = upload(TestClient(app), sample_pdf_bytes)
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    assert r.json()["total"] > 0


# ---------------------------------------------------------------- report
def test_unknown_report_is_404(client):
    r = client.get("/report/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert r.json()["detail"] == "Report not found"


# ---------------------------------------------------------------- startup
def test_startup_survives_a_broken_sbert_model(db_session, monkeypatch):
    """The lifespan warm-up must never take the app down. If the model explodes,
    the process still boots and scoring degrades to BM25."""
    import app.main as main

    monkeypatch.setattr(main, "warm_semantic_model",
                        lambda: (_ for _ in ()).throw(RuntimeError("weights corrupt")))
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as c:          # context manager = lifespan actually runs
            assert c.get("/llm/health").status_code == 200
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------- misc
def test_llm_health_disabled_without_key(client):
    r = client.get("/llm/health")
    assert r.status_code == 200
    assert r.json() == {"llm": "disabled"}


@pytest.mark.parametrize("role,expected", [
    ("frontend developer", "React"),
    ("FRONTEND DEVELOPER", "React"),   # lookup is case-insensitive
    ("backend developer", "FastAPI"),
    ("underwater basket weaver", "Git"),  # unknown role falls back to generics
])
def test_skills_suggest(client, role, expected):
    r = client.get("/skills/suggest", params={"role": role})
    assert r.status_code == 200
    skills = r.json()["skills"]
    assert skills and expected in skills


# ---------------------------------------------------------------- auth
PROTECTED = [("post", "/auth/sync", {}), ("post", "/resumes", {"basics": {}}),
             ("get", "/resumes", None), ("get", "/resumes/some-id", None)]


@pytest.mark.parametrize("method,path,body", PROTECTED)
def test_protected_routes_reject_anonymous_when_firebase_unconfigured(client, method, path, body):
    """conftest points FIREBASE_CREDENTIALS at a nonexistent file, so the real
    dependency answers 503 ("not configured") before it ever looks for a token."""
    r = getattr(client, method)(path, **({"json": body} if body is not None else {}))
    assert r.status_code == 503, f"{path} -> {r.status_code}"


@pytest.mark.parametrize("method,path,body", PROTECTED)
def test_protected_routes_401_without_token(client, monkeypatch, method, path, body):
    """With Firebase configured, a missing bearer token is a 401."""
    monkeypatch.setattr(auth, "_init_firebase", lambda: True)
    r = getattr(client, method)(path, **({"json": body} if body is not None else {}))
    assert r.status_code == 401, f"{path} -> {r.status_code}"


def test_protected_route_401_with_bad_token(client, monkeypatch):
    monkeypatch.setattr(auth, "_init_firebase", lambda: True)
    r = client.get("/resumes", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_score_endpoint_works_logged_out(client):
    r = client.post("/score", json={
        "resume": {"skills": ["Python"], "work": [{}], "education": [{}], "projects": [{}],
                   "raw_text": "Python engineer", "word_count": 2},
        "job_description": None,
    })
    assert r.status_code == 200, r.text
    assert r.json()["suggestionsSource"] == "rules"
