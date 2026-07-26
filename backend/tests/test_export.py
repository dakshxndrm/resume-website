"""PDF export: real PDF bytes out, readable 4xx for an empty resume.

ATS-friendliness is asserted the only way that matters mechanically — the text
must come back out of the finished PDF. Fitz (already a dependency) re-reads it.
"""
import fitz
import pytest

from app.services.pdf_export import is_empty_resume, safe_filename

FULL_RESUME = {
    "basics": {
        "name": "Jane Doe", "label": "Backend Engineer", "email": "jane@example.com",
        "phone": "+91 90000 00000", "location": "Bangalore, India",
        "url": "github.com/janedoe", "summary": "Backend engineer who ships reliable APIs.",
        "links": ["linkedin.com/in/janedoe"],
    },
    "work": [{
        "company": "Acme Corp", "position": "Software Engineer",
        "startDate": "Jan 2022", "endDate": "Dec 2023",
        "highlights": ["Cut p95 latency 40% with Redis caching.", "Built REST APIs in FastAPI."],
    }],
    "education": [{
        "institution": "PES University", "area": "Computer Science", "studyType": "B.Tech",
        "startDate": "2019", "endDate": "2023", "score": "8.7 CGPA",
    }],
    "projects": [{
        "name": "Resume Scanner", "description": "Next.js front end over a Python service.",
        "highlights": ["Parsed 10k resumes."], "url": "github.com/janedoe/scanner",
    }],
    "skills": ["Python", "FastAPI", "PostgreSQL"],
    "certifications": ["AWS Solutions Architect"],
}

EMPTY_RESUME = {"basics": {"name": "", "label": "", "email": ""},
                "work": [], "education": [], "projects": [], "skills": [], "certifications": []}


def export(client, resume):
    return client.post("/resumes/export", json=resume)


# ---------------------------------------------------------------- happy path
def test_export_returns_a_pdf(client):
    r = export(client, FULL_RESUME)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF"), "must be a real PDF, not JSON or an error page"
    assert len(r.content) > 1000


def test_exported_pdf_has_selectable_text_not_an_image(client):
    """Re-extract the text: an ATS parser has to be able to do exactly this."""
    r = export(client, FULL_RESUME)
    with fitz.open(stream=r.content, filetype="pdf") as doc:
        assert doc.page_count == 1
        text = "\n".join(page.get_text("text") for page in doc)
        assert not doc[0].get_images(), "no images — text must not be baked into graphics"

    for expected in ("Jane Doe", "Backend Engineer", "jane@example.com", "Acme Corp",
                     "PES University", "Resume Scanner", "Python", "FastAPI",
                     "AWS Solutions Architect", "Cut p95 latency 40%"):
        assert expected in text, f"{expected!r} missing from the exported PDF text"

    for heading in ("SUMMARY", "EXPERIENCE", "EDUCATION", "PROJECTS", "SKILLS"):
        assert heading in text


def test_export_filename_header(client):
    r = export(client, FULL_RESUME)
    assert r.headers["content-disposition"] == 'attachment; filename="Jane_Doe.pdf"'


def test_export_needs_no_auth_and_no_database(client):
    """Editing works logged out, so exporting must too — no token is sent here."""
    assert export(client, FULL_RESUME).status_code == 200


# ---------------------------------------------------------------- validation
def test_export_empty_resume_is_readable_4xx(client):
    r = export(client, EMPTY_RESUME)
    assert 400 <= r.status_code < 500
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert isinstance(detail, str) and "add your name" in detail.lower()


def test_export_missing_basics_is_422_not_500(client):
    r = client.post("/resumes/export", json={"work": []})
    assert r.status_code == 422


def test_export_minimal_resume_works(client):
    """One filled field is enough — only a completely blank resume is rejected."""
    r = export(client, {**EMPTY_RESUME, "basics": {"name": "A", "label": "", "email": ""}})
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")


# ---------------------------------------------------------------- unit-level
@pytest.mark.parametrize("resume,expected", [
    (EMPTY_RESUME, True),
    ({"basics": {}}, True),
    ({**EMPTY_RESUME, "skills": ["Python"]}, False),
    ({**EMPTY_RESUME, "basics": {"summary": "hi"}}, False),
    (FULL_RESUME, False),
])
def test_is_empty_resume(resume, expected):
    assert is_empty_resume(resume) is expected


@pytest.mark.parametrize("raw,expected", [
    ("Jane Doe", "Jane_Doe.pdf"),
    ("../../etc/passwd", "etc_passwd.pdf"),          # no path traversal
    ('evil" ; rm -rf /', "evil_rm_-rf.pdf"),         # no quotes/spaces to break the header
    ("", "resume.pdf"),
    ("   ", "resume.pdf"),
])
def test_safe_filename(raw, expected):
    assert safe_filename(raw) == expected


def test_blank_and_marker_prefixed_bullets_are_normalized(client):
    """The editor keeps blank lines while you type; the PDF must not show them,
    and a pasted "- " marker must not double up with the drawn bullet."""
    r = export(client, {**FULL_RESUME, "work": [{
        **FULL_RESUME["work"][0],
        "highlights": ["- Pasted with a dash marker", "", "   ", "• Pasted with a bullet"],
    }]})
    assert r.status_code == 200
    with fitz.open(stream=r.content, filetype="pdf") as doc:
        text = doc[0].get_text("text")
    assert "Pasted with a dash marker" in text
    assert "- Pasted" not in text and "•• " not in text


def test_export_survives_hostile_text(client):
    """Resume content is user input — XML-ish text must not break reportlab markup."""
    r = export(client, {**FULL_RESUME, "basics": {
        **FULL_RESUME["basics"], "summary": "C++ & <b>bold</b> <not-a-tag> R&D 100% >_<",
    }})
    assert r.status_code == 200
    with fitz.open(stream=r.content, filetype="pdf") as doc:
        assert "R&D" in doc[0].get_text("text")


def test_long_resume_paginates_instead_of_truncating(client):
    """Platypus must flow onto page 2 rather than silently dropping content."""
    big = {**FULL_RESUME, "work": [{
        "company": f"Company {i}", "position": "Engineer",
        "startDate": "2020", "endDate": "2021",
        "highlights": ["Delivered a substantial amount of measurable impact here."] * 4,
    } for i in range(12)]}

    r = export(client, big)
    assert r.status_code == 200
    with fitz.open(stream=r.content, filetype="pdf") as doc:
        assert doc.page_count >= 2
        text = "\n".join(p.get_text("text") for p in doc)
    assert "Company 0" in text and "Company 11" in text
