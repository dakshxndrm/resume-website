"""Normalise public resume / job-description corpora into one JSONL file.

Output format, one object per line:
    {"text": "...", "type": "resume"}   or   {"type": "job"}

Every record is PII-scrubbed (ml/data/scrub.py) and OCR-quality-filtered before
it is written. Nothing skips those two steps.

No credentials anywhere. Kaggle and Mendeley downloads are manual steps you do
once (see ml/README.md); this script only reads files already sitting in
<repo>/data/raw/. Hugging Face sources are public and fetched on demand.

    python ml/data/prepare.py --list
    python ml/data/prepare.py --out ml/data/corpus.jsonl
    python ml/data/prepare.py --hf --out ml/data/corpus.jsonl
    python ml/data/prepare.py --self-check
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scrub import (MAX_BROKEN_WORD_RATIO, MIN_ALPHA_RATIO, alpha_ratio,  # noqa: E402
                   broken_word_ratio, has_residual_pii, is_usable, scrub)

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"

# --------------------------------------------------------------------------
# Manual-download sources. `filename` is relative to data/raw/.
# `column` is the text column; `kind` is what those rows are.
# `licence` is recorded here and mirrored in ml/README.md - read that section
# before using any of this commercially.
# --------------------------------------------------------------------------
MANUAL_SOURCES = [
    {
        "filename": "Resume-Classification-Dataset.csv",
        "column": "Text",
        "kind": "resume",
        "expected": 13389,
        "where": "GitHub: noran-mohamed/Resume-Classification-Dataset",
        "licence": "UNCLEAR - scraped from LiveCareer/Google/Bing, no stated licence",
        "note": "OCR-extracted, real people's resumes. Heaviest scrubbing burden.",
    },
    {
        "filename": "resume_dataset.csv",
        "column": "Resume_str",
        "kind": "resume",
        "expected": 2482,
        "where": "Kaggle: snehaanbhawal/resume-dataset",
        "licence": "CC0 1.0 (per dataset page) - verify before commercial use",
        "note": "LiveCareer-sourced HTML->text; overlaps source 1, dedupe handles it.",
    },
    {
        "filename": "CareerCorpus.csv",  # .xlsx is what Mendeley ships; both are read
        "column": "resume_text",
        "kind": "resume",
        "expected": 302,
        "where": "Mendeley Data: wzzwn37gmd (CareerCorpus) - doi 10.17632/wzzwn37gmd.1",
        "licence": "CC BY 4.0 - attribution required",
        "note": "Ships as ONE .xlsx, six occupational categories. Column names are not "
                "published, so COLUMN_ALIASES guesses; --list prints the real headers "
                "if none match. Carries two expert scores per resume - that makes it "
                "eval/distillation label data, not pretraining volume.",
    },
    {
        "filename": "UpdatedResumeDataSet.csv",
        "column": "Resume",
        "kind": "resume",
        "expected": 962,
        "where": "Kaggle: gauravduttakiit/resume-dataset",
        "licence": "CC0 1.0 (per dataset page)",
        "note": "Older, short records; many fall under MIN_CHARS.",
    },
    {
        "filename": "job_descriptions.csv",
        "column": "job_description",
        "kind": "job",
        "expected": None,
        "where": "Kaggle: ravindrasinghrana/job-description-dataset",
        "licence": "CC0 1.0 (per dataset page)",
        "note": "Job side of the corpus, not resumes.",
    },
]

# Public Hugging Face datasets - no login, downloaded on demand with --hf.
HF_SOURCES = [
    {"path": "jacob-hugging-face/job-descriptions", "split": "train",
     "column": "job_description", "kind": "job",
     "licence": "unstated on the dataset card"},
    {
        # 2,164 real (anonymised) working histories, up to 17 chronological
        # experiences each, every position tagged with an ESCO occupation (v1.1.1).
        # One row is a whole career path, so several columns join into one document
        # rather than one column being the document - hence "columns"/join.
        # The card does not publish a column list; these are candidates, and the
        # loader prints the real schema when none match.
        "path": "jensjorisdecorte/anonymous-working-histories",
        "split": "train",
        "columns": ["experiences", "job_title", "title", "position", "description",
                    "job_description", "esco_occupation_title", "occupation"],
        "kind": "resume",
        "expected": 2164,
        "licence": "CC BY 4.0 - attribution required",
        "note": "Structured work history, not resume prose: no summary, skills or "
                "education sections. Useful for the experience-section language, "
                "weaker as whole-resume pretraining text.",
    },
]

# Column-name fallbacks: these CSVs get re-uploaded with renamed headers often
# enough that hard-failing on one name wastes an afternoon.
COLUMN_ALIASES = {
    "Text": ["Text", "text", "resume_text", "Resume", "Resume_str", "content"],
    "Resume_str": ["Resume_str", "Resume", "resume_text", "Text", "text"],
    "resume_text": ["resume_text", "Resume", "Text", "text", "resume", "CV",
                    "Resume Text", "Resume_str", "cv_text"],
    "Resume": ["Resume", "resume_text", "Text", "text"],
    "job_description": ["job_description", "Job Description", "description", "jd"],
}

MIN_CHARS = 120   # shorter than this is a header row or a scrape failure
MAX_CHARS = 40000  # longer than this is a concatenation bug, not a resume

# --------------------------------------------------------------------------
# Access-restricted, documented but not automated.
# --------------------------------------------------------------------------
RESTRICTED_SOURCES = [
    {
        "name": "OpenResume",
        "where": "https://zenodo.org/records/14726170",
        "status": "ACCESS RESTRICTED - request required, not automated here",
        "process": (
            "Zenodo restricted record. Click 'Request access' on the record page and "
            "state the purpose (research use, resume-matching model pretraining). The "
            "depositor approves manually; expect days to weeks, and expect the terms "
            "to prohibit redistribution. Do NOT block the pretraining track on it."
        ),
    },
]


def clean(text: str) -> str:
    """Collapse whitespace and strip control junk left by PDF/HTML scrapers.

    Newlines are preserved - the scrubber's name/address heuristics read line
    layout, so flattening first would blind them. Collapsing to single spaces
    happens per line instead.
    """
    text = str(text).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def resolve_column(df, source: dict) -> str | None:
    """Find the text column, tolerating the header renames these CSVs go through."""
    for candidate in COLUMN_ALIASES.get(source["column"], [source["column"]]):
        if candidate in df.columns:
            return candidate
    return None


def resolve_path(filename: str) -> Path | None:
    """Accept the file in whatever format the source actually ships.

    CareerCorpus is distributed as a single .xlsx, not a .csv, so insisting on one
    extension means a correctly-downloaded file is reported as missing.
    """
    exact = RAW_DIR / filename
    if exact.exists():
        return exact
    for suffix in (".xlsx", ".xls", ".csv"):
        alt = exact.with_suffix(suffix)
        if alt.exists():
            return alt
    return None


def read_table(path: Path):
    """One DataFrame from a CSV or a multi-sheet Excel workbook."""
    import pandas as pd

    if path.suffix.lower() in (".xlsx", ".xls"):
        # sheet_name=None -> every sheet; CareerCorpus splits its six occupational
        # categories across sheets, and dropping five of them would be silent loss.
        sheets = pd.read_excel(path, sheet_name=None)
        return pd.concat(sheets.values(), ignore_index=True) if sheets else pd.DataFrame()
    return pd.read_csv(path)


def load_manual(source: dict) -> list[dict]:
    path = resolve_path(source["filename"])
    if path is None:
        print(f"  skip  {source['filename']:<34} not in data/raw/  ({source['where']})")
        return []

    df = read_table(path)
    column = resolve_column(df, source)
    if column is None:
        print(f"  skip  {source['filename']:<34} no text column; "
              f"found {list(df.columns)[:6]}")
        return []

    expected = source.get("expected")
    warn = ""
    if expected and abs(len(df) - expected) > max(50, expected * 0.05):
        warn = f"  (expected ~{expected} - different version?)"
    print(f"  load  {path.name:<34} {len(df)} rows, column {column!r}{warn}")

    return [{"text": t, "type": source["kind"], "source": source["filename"]}
            for t in df[column].dropna()]


def load_hf(source: dict) -> list[dict]:
    from datasets import load_dataset

    print(f"  load  hf:{source['path']} ...")
    ds = load_dataset(source["path"], split=source["split"])
    return [{"text": r[source["column"]], "type": source["kind"], "source": source["path"]}
            for r in ds if r.get(source["column"])]


def process(records: list[dict]) -> tuple[list[dict], dict]:
    """Clean -> scrub -> quality-filter -> dedupe. Returns (kept, statistics).

    Order matters. Scrubbing runs before the quality filter so that a document
    rejected for OCR noise was never held in a scrubbed-vs-unscrubbed limbo, and
    dedupe runs last so two copies differing only in a phone number collapse.
    """
    stats = {"in": len(records), "too_short": 0, "too_long": 0, "ocr_rejected": 0,
             "duplicates": 0, "residual_pii": 0, "kept": 0}
    per_source: dict[str, dict[str, int]] = {}
    alpha_samples: list[float] = []

    seen: set[str] = set()
    kept: list[dict] = []
    for record in records:
        origin = record.get("source", "?")
        bucket = per_source.setdefault(origin, {"in": 0, "ocr_rejected": 0, "kept": 0})
        bucket["in"] += 1

        text = clean(record["text"])
        if len(text) < MIN_CHARS:
            stats["too_short"] += 1
            continue
        if len(text) > MAX_CHARS:
            stats["too_long"] += 1
            continue

        text = scrub(text)  # PII out before anything else looks at it
        alpha_samples.append(alpha_ratio(text))

        if not is_usable(text):
            stats["ocr_rejected"] += 1
            bucket["ocr_rejected"] += 1
            continue
        if len(text) < MIN_CHARS:  # scrubbing can shrink a mostly-contact-details record
            stats["too_short"] += 1
            continue

        key = text[:400]
        if key in seen:
            stats["duplicates"] += 1
            continue
        seen.add(key)

        if has_residual_pii(text):
            stats["residual_pii"] += 1  # counted, not dropped - see ml/README.md

        kept.append({"text": text, "type": record["type"]})
        bucket["kept"] += 1

    stats["kept"] = len(kept)
    stats["per_source"] = per_source
    stats["median_alpha_ratio"] = (
        sorted(alpha_samples)[len(alpha_samples) // 2] if alpha_samples else 0.0)
    return kept, stats


def report(stats: dict) -> None:
    total_in = stats["in"]
    pct = (lambda n: f"{n / total_in:5.1%}" if total_in else "    -")
    print(f"\n  read              {total_in:>7}")
    print(f"  too short (<{MIN_CHARS})  {stats['too_short']:>7}  {pct(stats['too_short'])}")
    print(f"  too long (>{MAX_CHARS})  {stats['too_long']:>7}  {pct(stats['too_long'])}")
    print(f"  OCR-rejected      {stats['ocr_rejected']:>7}  {pct(stats['ocr_rejected'])}"
          f"   (alpha<{MIN_ALPHA_RATIO} or broken-words>{MAX_BROKEN_WORD_RATIO})")
    print(f"  duplicates        {stats['duplicates']:>7}  {pct(stats['duplicates'])}")
    print(f"  KEPT              {stats['kept']:>7}  {pct(stats['kept'])}")
    print(f"  median alpha ratio  {stats['median_alpha_ratio']:.3f}")
    if stats["residual_pii"]:
        print(f"  WARNING: {stats['residual_pii']} kept documents still match an "
              "email/phone/URL pattern after scrubbing - inspect before sharing")

    if len(stats.get("per_source", {})) > 1:
        print("\n  per source:")
        for name, b in stats["per_source"].items():
            share = f"{b['ocr_rejected'] / b['in']:.1%}" if b["in"] else "-"
            print(f"    {name:<38} in {b['in']:>6}  ocr-rejected {share:>6}  "
                  f"kept {b['kept']:>6}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="ml/data/corpus.jsonl", help="output JSONL path")
    ap.add_argument("--hf", action="store_true",
                    help="also download the public Hugging Face sources")
    ap.add_argument("--list", action="store_true",
                    help="print expected sources, licences and status, then exit")
    args = ap.parse_args()

    if args.list:
        print(f"data/raw/ = {RAW_DIR}\n\nManual (download yourself - see ml/README.md):")
        for s in MANUAL_SOURCES:
            mark = "OK " if (RAW_DIR / s["filename"]).exists() else "-- "
            count = f"~{s['expected']}" if s["expected"] else "?"
            print(f"  {mark}{s['filename']:<34} {count:>7}  {s['where']}")
            print(f"      licence: {s['licence']}")
        print("\nAuto (--hf):")
        for s in HF_SOURCES:
            print(f"      {s['path']}  (licence: {s['licence']})")
        print("\nRestricted (manual request, not automated):")
        for s in RESTRICTED_SOURCES:
            print(f"      {s['name']}: {s['status']}\n      {s['where']}")
        return

    records: list[dict] = []
    for source in MANUAL_SOURCES:
        records += load_manual(source)
    if args.hf:
        for source in HF_SOURCES:
            records += load_hf(source)

    if not records:
        print("\nNothing to read. Put datasets in data/raw/ or pass --hf.")
        print("Run --list to see what is expected and where to get it.")
        print("ml/data/sample.jsonl (20 fake records) works for smoke tests meanwhile.")
        return

    kept, stats = process(records)
    report(stats)

    if not kept:
        print("\nEverything was filtered out - nothing written.")
        return

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for r in kept:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    resumes = sum(1 for r in kept if r["type"] == "resume")
    print(f"\nwrote {len(kept)} records to {out_path} "
          f"({resumes} resume / {len(kept) - resumes} job)")
    print(f"progress to the 50,000-document pretraining target: "
          f"{len(kept)}/50000 = {len(kept) / 50000:.1%}")


def _self_check() -> None:
    """python ml/data/prepare.py --self-check - the pipeline, on fixtures."""
    assert clean("a\t b\r\nc\x00d") == "a b\nc d", repr(clean("a\t b\r\nc\x00d"))
    assert clean("x\n\n\n\n\ny") == "x\n\ny"

    sample = Path(__file__).parent / "sample.jsonl"
    rows = [json.loads(line) for line in sample.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 20 and {r["type"] for r in rows} == {"resume", "job"}
    assert all(len(r["text"]) >= MIN_CHARS for r in rows)

    # a realistic mini-batch through the full pipeline
    pii = ("JANE DOE\njane.doe@example.com\n+44 7700 900123\n\nEXPERIENCE\n"
           "Backend engineer, 2019 - 2023. Built Python services in FastAPI and "
           "PostgreSQL, deployed with Docker on AWS, and owned the CI/CD pipeline.")
    junk = "|_l1 ;: !I 4^ }{ 0O ;;; ~~ ][ %$# ||| §§ ¬¬ >> << ** ;; " * 8
    batch = [
        {"text": pii, "type": "resume", "source": "t"},
        {"text": pii, "type": "resume", "source": "t"},          # exact duplicate
        {"text": junk, "type": "resume", "source": "t"},         # OCR garbage
        {"text": "too short", "type": "resume", "source": "t"},  # under MIN_CHARS
    ]
    kept, stats = process(batch)

    assert stats["kept"] == 1, stats
    assert stats["duplicates"] == 1 and stats["ocr_rejected"] == 1 and stats["too_short"] == 1
    body = kept[0]["text"]
    for leak in ("JANE DOE", "jane.doe@example.com", "7700 900123"):
        assert leak not in body, leak
    assert "FastAPI" in body and "2019 - 2023" in body, "signal was destroyed"
    assert stats["residual_pii"] == 0

    print("prepare self-check ok")


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        _self_check()
    else:
        main()
