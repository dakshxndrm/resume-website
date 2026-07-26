"""Shared test fixtures.

Three hard rules this file enforces for the whole suite:
  1. No network. GROQ_API_KEY is blanked for every test (autouse), so the Groq
     path short-circuits before requests.post is ever reached.
  2. No real database. DATABASE_URL is replaced with a dummy Postgres URL before
     app.core.db is imported (create_engine never connects, so nothing dials out),
     and every route test gets an in-memory SQLite session via a get_db override.
  3. No real secrets. The env vars below are set before app.core.config builds
     `settings`, and env always wins over backend/.env in pydantic-settings —
     so the real .env is never the source of any value the tests depend on.
"""
from __future__ import annotations

import io
import os

# --- must run BEFORE any "app.*" import (settings + engine are built at import) ---
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_never_connected"
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["FIREBASE_CREDENTIALS"] = "./__no_such_firebase_creds__.json"

import fitz  # noqa: E402  PyMuPDF
import pytest  # noqa: E402
from docx import Document  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import models  # noqa: E402,F401  registers tables on Base


# ---------------------------------------------------------------- no network
@pytest.fixture(autouse=True)
def _no_groq_key(monkeypatch):
    """`settings` is already built by import time, so blank the attribute too."""
    monkeypatch.setattr(settings, "groq_api_key", "", raising=False)


# ---------------------------------------------------------------- database
@pytest.fixture
def db_session():
    """In-memory SQLite session. StaticPool keeps one connection, so the schema
    created here is the same one the request sees."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session):
    """TestClient with get_db pointed at SQLite. Not used as a context manager on
    purpose: that would fire main.py's startup event and try to reach Neon."""
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------- fixture docs
SAMPLE_RESUME_TEXT = """JANE DOE
Bangalore, India | jane.doe@example.com | github.com/janedoe

EDUCATION
B.Tech in Computer Science, PES University, 2019 - 2023
CGPA 8.7/10

EXPERIENCE
Software Engineer Intern, Acme Corp - Jan 2022 - Dec 2022
Built REST APIs in Python and FastAPI backed by PostgreSQL.
Cut p95 latency 40% by adding Redis caching.

Backend Developer, Globex - 2023 - Present
Shipped Docker images through a CI/CD pipeline on AWS.
Wrote unit tests and reviewed pull requests in Git.

PROJECTS
Resume Scanner - a Next.js and TypeScript front end over a Python service.
Sentiment Dashboard - project using Pandas and NumPy for data analysis.

SKILLS
Python, JavaScript, TypeScript, SQL, React, Next.js, FastAPI, PostgreSQL,
Docker, Redis, AWS, CI/CD, Git, Linux, Pandas, NumPy, C++, Communication
"""


@pytest.fixture
def sample_resume_text() -> str:
    return SAMPLE_RESUME_TEXT


@pytest.fixture
def sample_pdf_bytes(sample_resume_text) -> bytes:
    return make_pdf(sample_resume_text)


@pytest.fixture
def sample_docx_bytes(sample_resume_text) -> bytes:
    return make_docx(sample_resume_text)


def make_pdf(text: str) -> bytes:
    """Real PDF bytes, generated in memory — no binary fixtures in the repo."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(40, 40, 560, 800), text, fontsize=9)
    data = doc.tobytes()
    doc.close()
    return data


def make_docx(text: str) -> bytes:
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
