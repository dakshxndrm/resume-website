"""PII scrubbing for the pretraining corpus.

The OCR resume corpora are real resumes belonging to real people, scraped from
job boards. They contain names, phone numbers, email addresses and profile links
inline in the text. Nothing goes into a training JSONL until it has been through
here.

Why this is separate from backend/app/services/privacy.py, which does a similar
job: the ml/ track is deliberately isolated from the web app and has its own
virtualenv, so it cannot import from backend/. The two differ in what they can
assume, too — the backend knows the account holder's name and can redact it
literally, while here we have a bare text blob and must guess.

What it catches:
  - email addresses
  - phone numbers (international, US, Indian formats)
  - URLs and bare social profile paths
  - postal-ish address lines and standalone name lines (heuristic, see below)

What it does NOT catch, stated plainly: this is regex and layout heuristics, not
named-entity recognition. A person's name in the middle of a sentence ("managed a
team under Sarah Klein") survives. For a *pretraining* corpus that residual is a
tolerable risk — the model learns embeddings, not a lookup table — but it is not
zero, and it is the reason this corpus should not be redistributed.
ponytail: regex + layout heuristics; swap in spaCy NER when Phase 2 pulls it in.
"""
from __future__ import annotations

import re

# Spaces are tolerated around the dots and the @: OCR routinely splits
# "maria.santos@example.org" into "maria .santos @ example .org".
EMAIL = re.compile(r"[\w+-]+(?:\s*\.\s*[\w+-]+)*\s*@\s*[\w-]+(?:\s*\.\s*[\w-]+)+")
URL = re.compile(
    r"\b(?:https?://|www\.)\S+"
    r"|\b(?:linkedin|github|gitlab|behance|dribbble|medium|twitter|x)\.com/\S+"
    r"|\b[\w-]+\.(?:com|io|dev|net|org|me|co\.uk|in)/\S+",
    re.I,
)
# 7+ digits with optional country code and separators. Bounded on both sides so
# it does not eat year ranges ("2019 - 2023") or metrics ("cut latency by 40%").
PHONE = re.compile(
    r"(?<![\d/])(?:\+\d{1,3}[\s.\-)]*)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{2,4}(?![\d/])"
)
# OCR often mangles the label but keeps the shape: "Phone : 98765 43210"
LABELLED_CONTACT = re.compile(
    r"(?i)\b(?:phone|mobile|cell|tel|telephone|contact|e-?mail|mail)\b\s*[:#-]?\s*\S.*"
)

# Layout heuristic for the header block. A resume's first lines are usually
# "JANE DOE" / "Jane Doe" alone on a line, sometimes followed by an address.
_NAME_LINE = re.compile(r"^[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){1,3}$")
_ALL_CAPS_NAME = re.compile(r"^[A-Z][A-Z'’.\- ]{3,40}$")
_ADDRESS_HINT = re.compile(
    r"(?i)\b(?:street|st\.|road|rd\.|avenue|ave\.|lane|apt|apartment|suite|block|"
    r"sector|nagar|colony|pincode|zip)\b|\b\d{5,6}(?:-\d{4})?\b"
)
# Words that look like a name line but are section headings, not people.
_HEADINGS = {
    "curriculum vitae", "resume", "summary", "professional summary", "objective",
    "career objective", "work experience", "professional experience", "experience",
    "education", "skills", "technical skills", "key skills", "projects",
    "certifications", "achievements", "personal details", "contact", "profile",
    "employment history", "core competencies", "areas of expertise", "references",
}

# How many leading lines count as "the header block" for name redaction. Names
# below that are left alone — they are usually referees or former managers, and
# blanking every capitalised pair would destroy company and technology names.
HEADER_LINES = 6


def _is_name_line(line: str) -> bool:
    stripped = line.strip(" \t|·•-–—:")
    if not stripped or stripped.lower() in _HEADINGS:
        return False
    if len(stripped) > 45 or any(ch.isdigit() for ch in stripped):
        return False
    return bool(_NAME_LINE.match(stripped) or _ALL_CAPS_NAME.match(stripped))


def scrub(text: str) -> str:
    """Redact PII from one resume. Returns the scrubbed text."""
    if not text:
        return ""

    lines = text.splitlines()
    out: list[str] = []
    for i, line in enumerate(lines):
        if LABELLED_CONTACT.search(line):
            # the whole line is a contact line; keep the label, drop the value
            line = re.sub(r"(?i)\b(phone|mobile|cell|tel|telephone|contact|e-?mail|mail)\b"
                          r"\s*[:#-]?\s*\S.*", r"\1: [redacted]", line)
        if i < HEADER_LINES:
            if _is_name_line(line):
                line = "[name]"
            elif _ADDRESS_HINT.search(line) and len(line.strip()) < 90:
                line = "[address]"
        out.append(line)

    text = "\n".join(out)
    text = EMAIL.sub("[email]", text)
    text = URL.sub("[url]", text)
    return PHONE.sub("[phone]", text)


def has_residual_pii(text: str) -> bool:
    """Cheap post-check: did an email/phone/URL survive? Used to count leaks."""
    return bool(EMAIL.search(text) or URL.search(text) or PHONE.search(text))


# --------------------------------------------------------------- OCR quality
def alpha_ratio(text: str) -> float:
    """Share of non-space characters that are letters.

    OCR failure looks like `|_l1 ;: !I` — punctuation and digit soup. Clean resume
    text sits around 0.80-0.90; a scanned-badly page drops well below 0.65.
    """
    body = [c for c in text if not c.isspace()]
    if not body:
        return 0.0
    return sum(c.isalpha() for c in body) / len(body)


def broken_word_ratio(text: str) -> float:
    """Share of alphabetic tokens that look like OCR debris.

    Single stray letters and long consonant runs ("rnanagernent" is fine, "lkjhg"
    is not) are the two cheap tells that survive lowercasing.
    """
    # skip letters glued to digits ("4.1s", "3x", "p95") — unit suffixes are not
    # OCR debris, and counting them as single-letter tokens punishes good text
    words = re.findall(r"(?<!\d)[A-Za-z]+", text)
    if not words:
        return 1.0
    bad = 0
    for w in words:
        low = w.lower()
        if len(low) == 1 and low not in "ai":
            bad += 1
        elif not re.search(r"[aeiou]", low) and len(low) > 3:
            bad += 1
    return bad / len(words)


def quality(text: str) -> dict[str, float]:
    return {"alpha_ratio": alpha_ratio(text), "broken_word_ratio": broken_word_ratio(text)}


# Thresholds, stated rather than buried. Tuned by eyeballing the tails of the
# LiveCareer/Bing OCR sets: below these the text is unreadable to a human too.
MIN_ALPHA_RATIO = 0.70
MAX_BROKEN_WORD_RATIO = 0.12


def is_usable(text: str) -> bool:
    return (alpha_ratio(text) >= MIN_ALPHA_RATIO
            and broken_word_ratio(text) <= MAX_BROKEN_WORD_RATIO)
