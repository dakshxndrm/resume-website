"""Normalise public resume / job-description corpora into one JSONL file.

Output format, one object per line:
    {"text": "...", "type": "resume"}   or   {"type": "job"}

No credentials anywhere. Kaggle datasets need a manual download (see ml/README.md);
this script only reads files you already placed in <repo>/data/raw/.
Hugging Face sources are public and downloaded automatically when you ask for them.

    python ml/data/prepare.py --list
    python ml/data/prepare.py --out ml/data/corpus.jsonl
    python ml/data/prepare.py --hf --out ml/data/corpus.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"

# Manual-download sources. filename is relative to data/raw/.
# column = the text column; kind = what those rows are.
MANUAL_SOURCES = [
    {
        "filename": "resume_dataset.csv",
        "column": "Resume_str",
        "kind": "resume",
        "where": "Kaggle: snehaanbhawal/resume-dataset (2.4k resumes)",
    },
    {
        "filename": "UpdatedResumeDataSet.csv",
        "column": "Resume",
        "kind": "resume",
        "where": "Kaggle: gauravduttakiit/resume-dataset (962 resumes)",
    },
    {
        "filename": "job_descriptions.csv",
        "column": "job_description",
        "kind": "job",
        "where": "Kaggle: ravindrasinghrana/job-description-dataset",
    },
]

# Public Hugging Face datasets - no login, downloaded on demand with --hf.
HF_SOURCES = [
    {"path": "jacob-hugging-face/job-descriptions", "split": "train",
     "column": "job_description", "kind": "job"},
]

MIN_CHARS = 120  # shorter than this is a header row or a scrape failure, not a document


def clean(text: str) -> str:
    """Collapse whitespace and strip control junk left by PDF/HTML scrapers."""
    text = re.sub(r"[\r\t\x00-\x08\x0b\x0c\x0e-\x1f]", " ", str(text))
    return re.sub(r"\s+", " ", text).strip()


def load_manual(source: dict) -> list[dict]:
    import pandas as pd

    path = RAW_DIR / source["filename"]
    if not path.exists():
        print(f"  skip {source['filename']:<28} not in data/raw/  ({source['where']})")
        return []
    df = pd.read_csv(path)
    if source["column"] not in df.columns:
        print(f"  skip {source['filename']:<28} no column {source['column']!r}; "
              f"found {list(df.columns)[:6]}")
        return []
    print(f"  load {source['filename']:<28} {len(df)} rows")
    return [{"text": t, "type": source["kind"]} for t in df[source["column"]].dropna()]


def load_hf(source: dict) -> list[dict]:
    from datasets import load_dataset

    print(f"  load hf:{source['path']} ...")
    ds = load_dataset(source["path"], split=source["split"])
    return [{"text": r[source["column"]], "type": source["kind"]}
            for r in ds if r.get(source["column"])]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="ml/data/corpus.jsonl", help="output JSONL path")
    ap.add_argument("--hf", action="store_true",
                    help="also download the public Hugging Face sources")
    ap.add_argument("--list", action="store_true",
                    help="print expected sources and exit")
    args = ap.parse_args()

    if args.list:
        print(f"data/raw/ = {RAW_DIR}\nManual (download yourself, see ml/README.md):")
        for s in MANUAL_SOURCES:
            mark = "OK " if (RAW_DIR / s["filename"]).exists() else "-- "
            print(f"  {mark}{s['filename']:<28} {s['where']}")
        print("Auto (--hf):")
        for s in HF_SOURCES:
            print(f"      {s['path']}")
        return

    records: list[dict] = []
    for source in MANUAL_SOURCES:
        records += load_manual(source)
    if args.hf:
        for source in HF_SOURCES:
            records += load_hf(source)

    # clean, drop stubs, dedupe (scraped corpora repeat the same posting a lot)
    seen: set[str] = set()
    out_records = []
    for r in records:
        text = clean(r["text"])
        if len(text) < MIN_CHARS or text in seen:
            continue
        seen.add(text)
        out_records.append({"text": text, "type": r["type"]})

    if not out_records:
        print("\nNothing to write. Put datasets in data/raw/ or pass --hf.")
        print("ml/data/sample.jsonl (20 fake records) works for smoke tests meanwhile.")
        return

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for r in out_records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    resumes = sum(1 for r in out_records if r["type"] == "resume")
    print(f"\nwrote {len(out_records)} records to {out_path} "
          f"({resumes} resume / {len(out_records) - resumes} job)")


def _self_check() -> None:
    """python ml/data/prepare.py --self-check - verifies clean() and the sample file."""
    assert clean("a\t b\r\nc\x00d") == "a b c d"
    sample = Path(__file__).parent / "sample.jsonl"
    rows = [json.loads(line) for line in sample.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 20, len(rows)
    assert {r["type"] for r in rows} == {"resume", "job"}
    assert all(len(r["text"]) >= MIN_CHARS for r in rows)
    print("self-check ok")


if __name__ == "__main__":
    import sys

    if "--self-check" in sys.argv:
        _self_check()
    else:
        main()
