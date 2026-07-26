"""ATS-friendly PDF export.

reportlab (not WeasyPrint): pure-Python wheels on Windows with no GTK/Cairo system
libraries to install, and Platypus gives automatic text wrapping + pagination for
free. Everything below is real selectable text in the base-14 Helvetica family —
no images, no tables, no text baked into graphics, single column top to bottom,
which is exactly what an ATS parser can read.
"""
from __future__ import annotations

import re
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

_INK = HexColor("#111827")
_MUTED = HexColor("#4B5563")

_NAME = ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=_INK)
_ROLE = ParagraphStyle("role", fontName="Helvetica", fontSize=11, leading=14, textColor=_MUTED, spaceAfter=2)
_CONTACT = ParagraphStyle("contact", fontName="Helvetica", fontSize=9, leading=12, textColor=_MUTED)
_HEADING = ParagraphStyle("heading", fontName="Helvetica-Bold", fontSize=10.5, leading=13,
                          textColor=_INK, spaceBefore=12, spaceAfter=2)
_ENTRY = ParagraphStyle("entry", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=_INK)
_META = ParagraphStyle("meta", fontName="Helvetica-Oblique", fontSize=9, leading=12, textColor=_MUTED)
_BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=13, textColor=_INK)
_BULLET = ParagraphStyle("bullet", parent=_BODY, leftIndent=12, bulletIndent=2, spaceBefore=1)


def _s(value: Any) -> str:
    """Escape a value for reportlab's mini-HTML paragraph markup."""
    return escape(str(value or "").strip())


def _joined(*parts: Any, sep: str = " | ") -> str:
    return sep.join(_s(p) for p in parts if str(p or "").strip())


def _date_range(start: Any, end: Any) -> str:
    start, end = str(start or "").strip(), str(end or "").strip()
    if not start and not end:
        return ""
    return f"{escape(start)} - {escape(end or 'Present')}"


def is_empty_resume(resume: dict[str, Any]) -> bool:
    """True when there is genuinely nothing to put on the page."""
    basics = resume.get("basics") or {}
    has_basics = any(str(basics.get(k) or "").strip() for k in ("name", "label", "email", "summary"))
    has_sections = any(resume.get(k) for k in ("work", "education", "projects", "skills", "certifications"))
    return not (has_basics or has_sections)


def safe_filename(name: str) -> str:
    """A resume name is user input — never let it steer the Content-Disposition header."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "").strip()).strip("._-")
    return f"{slug[:60] or 'resume'}.pdf"


def _bullets(items: Any) -> list:
    """Blank lines are dropped and any pasted "-"/"•" marker is stripped — the
    flowable draws its own bullet, so keeping theirs would double it up."""
    out = []
    for item in items or []:
        text = _s(re.sub(r"^[-•*]\s*", "", str(item or "").strip()))
        if text:
            out.append(Paragraph(text, _BULLET, bulletText="•"))
    return out


def _section(title: str, flowables: list) -> list:
    """A heading + rule, emitted only when the section actually has content."""
    if not flowables:
        return []
    return [Paragraph(title.upper(), _HEADING),
            HRFlowable(width="100%", thickness=0.6, color=_MUTED, spaceAfter=5),
            *flowables]


def build_resume_pdf(resume: dict[str, Any]) -> bytes:
    basics = resume.get("basics") or {}
    story: list = []

    # ---- header
    story.append(Paragraph(_s(basics.get("name")) or "Unnamed", _NAME))
    if str(basics.get("label") or "").strip():
        story.append(Paragraph(_s(basics.get("label")), _ROLE))
    contact = _joined(basics.get("email"), basics.get("phone"), basics.get("location"), basics.get("url"))
    if contact:
        story.append(Paragraph(contact, _CONTACT))
    links = [_s(x) for x in (basics.get("links") or []) if str(x or "").strip()]
    if links:
        story.append(Paragraph(" | ".join(links), _CONTACT))

    # ---- summary
    if str(basics.get("summary") or "").strip():
        story += _section("Summary", [Paragraph(_s(basics.get("summary")), _BODY)])

    # ---- experience
    entries: list = []
    for job in resume.get("work") or []:
        head = _joined(job.get("position"), job.get("company"), sep=" — ")
        if head:
            entries.append(Paragraph(head, _ENTRY))
        dates = _date_range(job.get("startDate"), job.get("endDate"))
        if dates:
            entries.append(Paragraph(dates, _META))
        entries += _bullets(job.get("highlights"))
        entries.append(Spacer(1, 6))
    story += _section("Experience", entries)

    # ---- education
    entries = []
    for edu in resume.get("education") or []:
        head = _joined(_joined(edu.get("studyType"), edu.get("area"), sep=" in "), edu.get("institution"), sep=" — ")
        if head:
            entries.append(Paragraph(head, _ENTRY))
        meta = _joined(_date_range(edu.get("startDate"), edu.get("endDate")), edu.get("score"))
        if meta:
            entries.append(Paragraph(meta, _META))
        entries.append(Spacer(1, 6))
    story += _section("Education", entries)

    # ---- projects
    entries = []
    for proj in resume.get("projects") or []:
        head = _joined(proj.get("name"), proj.get("url"), sep=" — ")
        if head:
            entries.append(Paragraph(head, _ENTRY))
        if str(proj.get("description") or "").strip():
            entries.append(Paragraph(_s(proj.get("description")), _BODY))
        entries += _bullets(proj.get("highlights"))
        entries.append(Spacer(1, 6))
    story += _section("Projects", entries)

    # ---- skills / certifications (plain comma lists: the format ATS parsers expect)
    skills = [_s(s) for s in (resume.get("skills") or []) if str(s or "").strip()]
    if skills:
        story += _section("Skills", [Paragraph(", ".join(skills), _BODY)])
    certs = [_s(c) for c in (resume.get("certifications") or []) if str(c or "").strip()]
    if certs:
        story += _section("Certifications", [Paragraph(", ".join(certs), _BODY)])

    buf = BytesIO()
    SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        title=f"{str(basics.get('name') or 'Resume')} — Resume",
        author=str(basics.get("name") or ""),
    ).build(story)
    return buf.getvalue()
