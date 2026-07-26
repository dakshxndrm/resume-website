"""Shared plumbing for the external benchmarks.

Everything here is measurement only. Nothing in this directory imports anything
writable from app/ — the scorer is called exactly as production calls it and is
never monkeypatched, reweighted or tuned.

The resume path deliberately goes text -> .docx bytes -> parse_resume(), which is
the real /score/upload pipeline including P1 parsing. DOCX rather than PDF on
purpose: PyMuPDF's insert_textbox silently truncates text that overflows the box,
which would quietly shrink the long-resume and keyword-stuffing cases and make the
benchmark lie. python-docx has no layout limit.
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# The scorer reads settings at import; keep it away from the real .env and Neon.
os.environ.setdefault("DATABASE_URL", "postgresql://eval:eval@localhost:5432/eval_unused")
os.environ.setdefault("GROQ_API_KEY", "")

from docx import Document  # noqa: E402

from app.services.parsing import extract_skills, parse_resume  # noqa: E402,F401
from app.services.scoring import WEIGHTS, score_resume  # noqa: E402,F401


def docx_bytes(text: str) -> bytes:
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def score_text(resume_text: str, job_description: str | None = None) -> dict:
    """Score plain resume text through the real parse + score pipeline."""
    parsed = parse_resume(docx_bytes(resume_text), "case.docx")
    return score_resume(parsed, job_description)


def categories_of(report: dict) -> dict[str, int]:
    return {c["key"]: c["score"] for c in report["categories"]}


def sbert_mode() -> str:
    """Which semantic path is live. Printed by every script — the numbers differ
    between the two modes, so a result without this line is not reproducible."""
    if os.getenv("SBERT_DISABLED"):
        return "SBERT_DISABLED=1 — lexical only (keyword coverage + BM25)"
    try:
        from app.services.scoring import _sbert

        model = _sbert()
    except Exception:
        model = None
    if model is None:
        return "SBERT unavailable — lexical only (keyword coverage + BM25)"
    from app.services.scoring import SBERT_MODEL

    return f"SBERT active — {SBERT_MODEL} (45% of the semantic component)"


# --------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------
def correlations(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """(spearman, pearson). NaN when a series is constant — correlation is
    undefined there, and reporting 0.0 would read as "measured, no relationship"."""
    from scipy.stats import pearsonr, spearmanr

    if len(xs) < 3:
        return float("nan"), float("nan")
    with_warnings_suppressed = (spearmanr(xs, ys).statistic, pearsonr(xs, ys).statistic)
    return with_warnings_suppressed


def distribution_report(scores: list[int], band: int = 15, threshold: float = 0.60) -> str:
    """Flag a scorer that rates everything roughly the same.

    A metric that puts >threshold of a diverse corpus inside a `band`-point window
    cannot rank candidates, no matter what its correlation says.
    """
    if not scores:
        return "no scores"
    ordered = sorted(scores)
    best_count, best_lo = 0, ordered[0]
    for lo in ordered:
        count = sum(1 for s in ordered if lo <= s <= lo + band)
        if count > best_count:
            best_count, best_lo = count, lo
    share = best_count / len(scores)

    lines = [
        f"  range      {ordered[0]} .. {ordered[-1]}  (spread {ordered[-1] - ordered[0]} points)",
        f"  median     {ordered[len(ordered) // 2]}",
        f"  densest {band}-point band: {best_lo}-{best_lo + band} holds "
        f"{best_count}/{len(scores)} ({share:.0%})",
    ]
    if share > threshold:
        lines.append(
            f"  *** FLAG: >{threshold:.0%} of resumes fall inside a {band}-point band. "
            f"The scorer is not discriminating between them. ***"
        )
    return "\n".join(lines)


def histogram(scores: list[int], width: int = 40) -> str:
    buckets: dict[int, int] = {}
    for s in scores:
        buckets[min(90, (s // 10) * 10)] = buckets.get(min(90, (s // 10) * 10), 0) + 1
    peak = max(buckets.values()) if buckets else 1
    rows = []
    for lo in range(0, 100, 10):
        n = buckets.get(lo, 0)
        rows.append(f"  {lo:>3}-{lo + 9:<3} {'█' * int(n / peak * width):<{width}} {n}")
    return "\n".join(rows)
