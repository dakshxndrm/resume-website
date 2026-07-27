"""Phase 0: consent capture, consent gating, and data deletion.

The rule these tests exist to defend: a TrainingExample row appears if and only if
the user explicitly opted in. Everything else about the product works identically
either way — refusing consent must cost the user nothing.
"""
import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user, get_optional_user
from app.core.db import get_db
from app.main import app
from app.models.models import ResumeRecord, ScoreReportRecord, TrainingExample, User

CLAIMS = {"uid": "firebase-uid-123", "email": "jane@example.com", "name": "Jane Doe"}

RESUME = {
    "basics": {"name": "Jane Doe", "email": "jane@example.com", "phone": "+91 98765 43210",
               "label": "Backend Engineer"},
    "skills": ["Python", "FastAPI"], "work": [{}], "education": [{}], "projects": [{}],
    "raw_text": "Jane Doe | jane@example.com | Backend engineer building APIs in Python.",
    "word_count": 12,
}
JD = "Backend Engineer. Python, FastAPI and PostgreSQL."


@pytest.fixture
def user(db_session):
    """A synced user row, consent off — the default every new account starts at."""
    row = User(firebase_uid=CLAIMS["uid"], email=CLAIMS["email"], name=CLAIMS["name"])
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


@pytest.fixture
def authed(db_session, user):
    """TestClient signed in as `user`. Firebase itself is never called — the auth
    dependency is overridden, which is the seam FastAPI provides for exactly this."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: CLAIMS
    app.dependency_overrides[get_optional_user] = lambda: CLAIMS
    yield TestClient(app)
    app.dependency_overrides.clear()


def _training_rows(db):
    return db.query(TrainingExample).all()


# ---------------------------------------------------------------- consent capture
def test_new_user_has_no_consent_by_default(authed, user):
    assert user.training_consent is False
    assert authed.get("/users/me").json()["trainingConsent"] is False


def test_consent_endpoint_sets_the_flag(authed, db_session, user):
    r = authed.patch("/users/consent", json={"training_consent": True})
    assert r.status_code == 200
    assert r.json() == {"trainingConsent": True}

    db_session.refresh(user)
    assert user.training_consent is True
    assert authed.get("/users/me").json()["trainingConsent"] is True


def test_consent_can_be_withdrawn(authed, db_session, user):
    authed.patch("/users/consent", json={"training_consent": True})
    r = authed.patch("/users/consent", json={"training_consent": False})

    assert r.json() == {"trainingConsent": False}
    db_session.refresh(user)
    assert user.training_consent is False


def test_consent_requires_auth(client):
    """conftest points FIREBASE_CREDENTIALS at nothing, so the real dependency 503s
    before it looks for a token — either way, no anonymous writes."""
    assert client.patch("/users/consent", json={"training_consent": True}).status_code == 503
    assert client.get("/users/me").status_code == 503


# ---------------------------------------------------------------- consent gating
def test_no_training_example_written_without_consent(authed, db_session):
    r = authed.post("/score", json={"resume": RESUME, "job_description": JD})

    assert r.status_code == 200
    assert _training_rows(db_session) == [], "wrote training data without consent"
    # ...and the user still got a complete report
    assert r.json()["total"] > 0 and r.json()["suggestions"]


def test_training_example_written_with_consent(authed, db_session):
    authed.patch("/users/consent", json={"training_consent": True})
    r = authed.post("/score", json={"resume": RESUME, "job_description": JD})
    report_id = r.json()["id"]

    rows = _training_rows(db_session)
    assert len(rows) == 1
    assert rows[0].report_id == report_id
    assert rows[0].teacher_output["total"] == r.json()["total"]


def test_stored_training_example_is_anonymised(authed, db_session):
    authed.patch("/users/consent", json={"training_consent": True})
    authed.post("/score", json={"resume": RESUME, "job_description": JD})

    stored = _training_rows(db_session)[0].anonymized_resume
    blob = str(stored)
    for leak in ("Jane Doe", "jane@example.com", "98765"):
        assert leak not in blob, leak
    assert stored["skills"] == ["Python", "FastAPI"], "skills are the training signal"
    assert stored["basics"]["label"] == "Backend Engineer"


def test_withdrawing_consent_stops_new_training_data(authed, db_session):
    authed.patch("/users/consent", json={"training_consent": True})
    authed.post("/score", json={"resume": RESUME, "job_description": JD})
    authed.patch("/users/consent", json={"training_consent": False})
    authed.post("/score", json={"resume": RESUME, "job_description": JD})

    assert len(_training_rows(db_session)) == 1, "kept collecting after withdrawal"


def test_uploads_are_gated_too(authed, db_session, sample_pdf_bytes):
    """The upload path is a second door into the same table — it needs the same lock."""
    files = {"file": ("resume.pdf", sample_pdf_bytes, "application/pdf")}
    assert authed.post("/score/upload", files=files).status_code == 200
    assert _training_rows(db_session) == []

    authed.patch("/users/consent", json={"training_consent": True})
    assert authed.post("/score/upload", files=files).status_code == 200
    assert len(_training_rows(db_session)) == 1


def test_refusing_consent_does_not_degrade_scoring(authed, db_session):
    """No dark patterns: the report must be byte-identical apart from its id/timestamp."""
    without = authed.post("/score", json={"resume": RESUME, "job_description": JD}).json()
    authed.patch("/users/consent", json={"training_consent": True})
    with_consent = authed.post("/score", json={"resume": RESUME, "job_description": JD}).json()

    drop = {"id", "createdAt"}
    assert {k: v for k, v in without.items() if k not in drop} == \
           {k: v for k, v in with_consent.items() if k not in drop}


def test_export_still_works_without_consent(authed):
    r = authed.post("/resumes/export", json={"basics": {"name": "Jane Doe"}, "skills": ["Python"]})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


# ---------------------------------------------------------------- deletion
def test_delete_removes_every_related_row(authed, db_session, user):
    authed.patch("/users/consent", json={"training_consent": True})
    authed.post("/resumes", json={"basics": {"name": "Jane Doe"}, "skills": ["Python"]})
    authed.post("/score", json={"resume": RESUME, "job_description": JD})

    # precondition: there is actually something to delete
    assert db_session.query(ResumeRecord).count() == 1
    assert db_session.query(ScoreReportRecord).count() == 1
    assert db_session.query(TrainingExample).count() == 1

    r = authed.delete("/users/me")
    assert r.status_code == 200
    assert r.json()["deleted"] == {"trainingExamples": 1, "scoreReports": 1,
                                   "resumes": 1, "cachedSuggestions": 0}

    db_session.expire_all()
    assert db_session.query(TrainingExample).count() == 0
    assert db_session.query(ScoreReportRecord).count() == 0
    assert db_session.query(ResumeRecord).count() == 0
    assert db_session.query(User).count() == 0


def test_delete_is_idempotent_from_the_users_point_of_view(authed):
    assert authed.delete("/users/me").status_code == 200
    # the row is gone, so the second call cannot find a user to delete
    assert authed.delete("/users/me").status_code == 404


def test_delete_requires_auth(client):
    assert client.delete("/users/me").status_code == 503


def test_delete_leaves_other_users_data_alone(authed, db_session):
    other = User(firebase_uid="someone-else", email="bob@example.com", name="Bob")
    db_session.add(other)
    db_session.commit()
    db_session.add(ResumeRecord(user_id=other.id, data={"basics": {"name": "Bob"}}))
    db_session.commit()

    authed.delete("/users/me")

    db_session.expire_all()
    assert db_session.query(User).count() == 1
    assert db_session.query(ResumeRecord).count() == 1
