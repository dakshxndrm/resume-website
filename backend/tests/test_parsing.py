"""Parsing service: text extraction from real in-memory PDF/DOCX, skill matching."""
from app.services.parsing import extract_skills, extract_text, parse_resume

PARSE_KEYS = {"raw_text", "skills", "work", "education", "projects", "word_count"}


# ---------------------------------------------------------------- extract_text
def test_extract_text_pdf(sample_pdf_bytes):
    text = extract_text(sample_pdf_bytes, "resume.pdf")
    for word in ("JANE DOE", "EXPERIENCE", "EDUCATION", "Python", "FastAPI"):
        assert word in text, f"{word!r} missing from extracted PDF text"


def test_extract_text_docx(sample_docx_bytes):
    text = extract_text(sample_docx_bytes, "resume.docx")
    for word in ("JANE DOE", "EXPERIENCE", "EDUCATION", "Python", "FastAPI"):
        assert word in text, f"{word!r} missing from extracted DOCX text"


def test_extract_text_garbage_returns_empty():
    """Corrupt bytes must degrade to "" — the route turns that into a 422."""
    assert extract_text(b"this is definitely not a pdf", "resume.pdf") == ""
    assert extract_text(b"\x00\x01\x02broken", "resume.docx") == ""


def test_extract_text_unsupported_extension(sample_pdf_bytes):
    assert extract_text(sample_pdf_bytes, "resume.txt") == ""
    assert extract_text(b"", "") == ""


# ---------------------------------------------------------------- extract_skills
def test_extract_skills_multiword_and_punctuated():
    text = "Skilled in Next.js, C++, CI/CD, Tailwind CSS, REST APIs and Node.js."
    found = extract_skills(text)
    for skill in ("Next.js", "C++", "CI/CD", "Tailwind CSS", "REST APIs", "Node.js"):
        assert skill in found


def test_extract_skills_no_substring_false_positives():
    """Whole-word matching: 'java' must not fall out of 'JavaScript', etc."""
    found = extract_skills("JavaScript, Rustic charm, Django, Goal setting, Ruby")
    assert "Javascript" in found
    assert "Java" not in found      # substring of JavaScript
    assert "Rust" not in found      # substring of Rustic
    assert "Go" not in found        # substring of Goal / Django
    assert "R" not in found         # single-letter skill must not match anywhere
    assert "Ruby" in found          # ...but a genuine whole word still matches


def test_extract_skills_case_insensitive_and_deduped():
    found = extract_skills("python PYTHON Python docker DOCKER")
    assert found.count("Python") == 1
    assert found.count("Docker") == 1


# ---------------------------------------------------------------- parse_resume
def test_parse_resume_shape_on_garbage():
    """Never raises, never returns a partial dict — the scorer depends on all six."""
    parsed = parse_resume(b"\xff\xfe garbage bytes", "resume.pdf")
    assert set(parsed) == PARSE_KEYS
    assert parsed["raw_text"] == ""
    assert parsed["skills"] == []
    assert parsed["word_count"] == 0


def test_parse_resume_shape_on_empty_input():
    parsed = parse_resume(b"", "whatever.xyz")
    assert set(parsed) == PARSE_KEYS


def test_parse_resume_on_sample_pdf(sample_pdf_bytes):
    parsed = parse_resume(sample_pdf_bytes, "resume.pdf")
    assert set(parsed) == PARSE_KEYS

    # plausible skill haul — enough to be real, not so many it's matching noise
    assert 6 <= len(parsed["skills"]) <= 40
    assert "Python" in parsed["skills"]
    assert "Docker" in parsed["skills"]

    # "2023 - Present" / "2019 - 2023" date ranges drive the entry heuristic
    assert len(parsed["work"]) >= 1
    assert len(parsed["education"]) >= 1
    assert parsed["word_count"] > 50


def test_parse_resume_on_sample_docx(sample_docx_bytes):
    parsed = parse_resume(sample_docx_bytes, "resume.docx")
    assert "Python" in parsed["skills"]
    assert len(parsed["work"]) >= 1
    assert parsed["word_count"] > 50
