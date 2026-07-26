"""PII scrubbing for consented training data (Phase 0 / Phase 4).

A TrainingExample is only ever written with explicit consent, and even then it
stores a scrubbed copy — the training signal is the *shape* of the resume
(skills, roles, wording), never who wrote it. Name, email, phone, address and
profile URLs are dropped before anything reaches the training table.

This is deliberately conservative: it over-redacts rather than under-redacts.
A false positive costs one mangled token in a training corpus; a false negative
puts someone's phone number in a dataset.

Known limitation, stated plainly rather than papered over: this is regex plus
literal redaction of identifiers we already know (the account name/email, the
resume's own `basics`). It is not named-entity recognition, so a person's name
appearing in body text — a referee, a colleague, a previous manager — can
survive. Phase 2 pulls in spaCy NER, which is the point to tighten this.
ponytail: regex + known-identifier redaction, upgrade to NER when spaCy lands.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

# Contact fields in the JSON Resume `basics` block. Everything here is identity,
# not signal — `label` (target role) and `summary` are kept on purpose.
_PII_BASICS = {"name", "email", "phone", "url", "image", "location", "profiles"}

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# 7+ digits with optional separators/country code — catches most phone shapes
# without eating dates ("2019 - 2023") or metrics ("cut latency 40%").
_PHONE = re.compile(r"(?<!\d)(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{2,4}(?!\d)")
_URL = re.compile(r"\b(?:https?://|www\.)\S+|\b[\w-]+\.(?:com|io|dev|net|org|me)/\S+", re.I)


def scrub_text(text: str, known: Iterable[str] = ()) -> str:
    """Replace emails, phone numbers, URLs and any known identifiers with placeholders.

    `known` is for values we already hold — the account name and email, the
    resume's own `basics.name`. Uploaded resumes are a raw text blob with no
    structure to key off, so this literal pass is what catches the name in them.
    """
    if not text:
        return ""
    # longest first, so "Jane Doe" is redacted before a bare "Jane" splits it
    for value in sorted({v.strip() for v in known if isinstance(v, str) and len(v.strip()) > 2},
                        key=len, reverse=True):
        text = re.sub(re.escape(value), "[redacted]", text, flags=re.I)
    text = _EMAIL.sub("[email]", text)
    text = _URL.sub("[url]", text)
    return _PHONE.sub("[phone]", text)


def anonymize_resume(resume: dict, known: Iterable[str] = ()) -> dict:
    """Copy of a resume with identifying fields removed and free text scrubbed.

    Handles both shapes the API sees: a structured JSON Resume from the editor,
    and the parser's output (which carries a `raw_text` blob).
    """
    resume = resume or {}
    out = {k: v for k, v in resume.items() if k != "basics"}

    basics = resume.get("basics")
    identifiers = list(known)
    if isinstance(basics, dict):
        # the resume's own contact block is the best source of what to redact
        identifiers += [basics.get(f) for f in ("name", "email", "phone")]
        kept = {k: v for k, v in basics.items() if k not in _PII_BASICS}
        if isinstance(kept.get("summary"), str):
            kept["summary"] = scrub_text(kept["summary"], identifiers)
        out["basics"] = kept

    if isinstance(out.get("raw_text"), str):
        out["raw_text"] = scrub_text(out["raw_text"], identifiers)
    return out


def _self_check() -> None:
    """python -m app.services.privacy — the redaction rules, exercised."""
    resume = {
        "basics": {"name": "Jane Doe", "email": "jane.doe@example.com",
                   "phone": "+91 98765 43210", "url": "github.com/janedoe",
                   "label": "Backend Engineer", "summary": "Reach me at jane@x.com"},
        "skills": ["Python"],
        "raw_text": "Jane Doe | jane.doe@example.com | +91 98765 43210 | github.com/janedoe\n"
                    "Cut p95 latency 40% in 2022 - 2023.",
    }
    out = anonymize_resume(resume)

    assert "name" not in out["basics"] and "email" not in out["basics"]
    assert out["basics"]["label"] == "Backend Engineer", "target role is signal, keep it"
    assert "jane@x.com" not in out["basics"]["summary"]
    assert out["skills"] == ["Python"], "skills are the whole point of the dataset"
    for leak in ("Doe", "jane.doe@example.com", "98765", "github.com/janedoe"):
        assert leak not in out["raw_text"], leak
    assert "40%" in out["raw_text"], "metrics must survive scrubbing"
    assert "2022 - 2023" in out["raw_text"], "date ranges are not phone numbers"

    # uploaded resumes have no basics block — the account identity is what we key off
    upload = {"raw_text": "JOHN SMITH\njohn@corp.io\nBackend engineer, 6 years.",
              "skills": ["Go"]}
    scrubbed = anonymize_resume(upload, known=["John Smith", "john@corp.io"])
    assert "JOHN SMITH" not in scrubbed["raw_text"] and "john@corp.io" not in scrubbed["raw_text"]
    assert "Backend engineer" in scrubbed["raw_text"]

    assert anonymize_resume({}) == {} and scrub_text("") == ""
    print("privacy self-check ok")


if __name__ == "__main__":
    _self_check()
