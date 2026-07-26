"""Measure extract_skills() against human NER skill annotations.

    python parsing_check.py --file data/resume-corpus.json

This validates P1 parsing directly and needs no scoring labels: the dataset marks
skill spans by hand, so we can ask what fraction of them the extractor finds.

Two recall numbers are reported, and the difference between them is the point:

  raw recall          of ALL annotated skill spans, how many were found.
                      Bounded above by vocabulary coverage — extract_skills only
                      knows the ~60 terms in SKILL_VOCAB, so every gold skill
                      outside that list is unfindable by construction.

  in-vocabulary       of the gold skills that DO appear in SKILL_VOCAB, how many
  recall              were found. This isolates matcher quality from vocabulary
                      size and is the number to fix regexes against.

Quoting raw recall alone would blame the matcher for a vocabulary problem.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from _harness import extract_skills

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.services.parsing import SKILL_VOCAB, _pretty_skill  # noqa: E402

SKILL_LABELS = {"skills", "skill", "technical skill", "technical skills", "tech skill"}


def load_annotations(path: Path) -> list[tuple[str, list[str]]]:
    """Return [(resume_text, [gold skill strings])].

    Handles the two shapes this corpus is published in:
      dataturks JSONL  {"content": ..., "annotation": [{"label": [...],
                        "points": [{"start","end","text"}]}]}
      spaCy JSON       [[text, {"entities": [[start, end, "LABEL"], ...]}], ...]
    """
    if not path.exists():
        sys.exit(f"Not found: {path}\nDownload it first — see external/README.md")

    raw = path.read_text(encoding="utf-8", errors="replace").strip()
    records: list = []
    try:
        parsed = json.loads(raw)
        records = parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        for line in raw.splitlines():                     # JSONL
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not records:
        sys.exit(f"Could not parse any records from {path}")

    out: list[tuple[str, list[str]]] = []
    for rec in records:
        # --- spaCy tuple form
        if isinstance(rec, list) and len(rec) == 2 and isinstance(rec[0], str):
            text, meta = rec
            gold = [text[s:e] for s, e, label in (meta or {}).get("entities", [])
                    if str(label).lower().replace("_", " ") in SKILL_LABELS]
            out.append((text, gold))
            continue

        # --- dataturks form
        if isinstance(rec, dict) and "content" in rec:
            text = rec["content"]
            gold = []
            for ann in rec.get("annotation") or []:
                labels = [str(x).lower().replace("_", " ") for x in (ann.get("label") or [])]
                if not any(lb in SKILL_LABELS for lb in labels):
                    continue
                for point in ann.get("points") or []:
                    span = (point.get("text") or "").strip()
                    if span:
                        gold.append(span)
            out.append((text, gold))

    if not out:
        sys.exit("Parsed the file but found no recognisable annotation records.")
    return out


def split_gold(span: str) -> list[str]:
    """One annotated span often lists many skills ('Python, SQL and Docker')."""
    parts = re.split(r"[,;/|•\n]| and ", span)
    return [p.strip(" .-\t") for p in parts if len(p.strip(" .-\t")) > 1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path, default=Path("data/resume-corpus.json"))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--show", type=int, default=25, help="how many misses to list")
    args = ap.parse_args()

    data = load_annotations(args.file)
    if args.limit:
        data = data[: args.limit]

    vocab = {s.lower() for s in SKILL_VOCAB}
    pretty_vocab = {_pretty_skill(s) for s in SKILL_VOCAB}

    gold_total = invocab_total = 0
    hit_total = invocab_hit = 0
    false_positives = Counter()
    missed_invocab = Counter()
    missed_outofvocab = Counter()
    per_resume: list[tuple[int, int]] = []

    for text, spans in data:
        gold = {g.lower() for span in spans for g in split_gold(span)}
        if not gold:
            continue
        found = {s.lower() for s in extract_skills(text)}
        found_pretty = set(extract_skills(text))

        gold_invocab = {g for g in gold if g in vocab}
        hits = {g for g in gold if g in found}

        gold_total += len(gold)
        hit_total += len(hits)
        invocab_total += len(gold_invocab)
        invocab_hit += len(gold_invocab & found)
        per_resume.append((len(hits), len(gold)))

        for g in gold_invocab - found:
            missed_invocab[g] += 1
        for g in gold - vocab:
            missed_outofvocab[g] += 1
        # a prediction is a false positive when the annotators marked no such skill
        for f in found_pretty:
            if f.lower() not in gold:
                false_positives[f] += 1

    if gold_total == 0:
        sys.exit("No skill annotations found — check the label names in this dump.")

    print("=" * 78)
    print("PARSING CHECK — extract_skills vs human NER annotations".center(78))
    print("=" * 78)
    print(f"file                  {args.file}")
    print(f"resumes with skills   {len(per_resume)}")
    print(f"vocabulary size       {len(SKILL_VOCAB)} terms in SKILL_VOCAB")

    raw_recall = hit_total / gold_total
    inv_recall = invocab_hit / invocab_total if invocab_total else float("nan")
    coverage = invocab_total / gold_total

    print("\n" + "-" * 78)
    print(f"gold skill mentions        {gold_total}")
    print(f"  of those in SKILL_VOCAB  {invocab_total}  ({coverage:.1%} vocabulary coverage)")
    print(f"  found by extract_skills  {hit_total}")
    print("-" * 78)
    print(f"RAW RECALL           {raw_recall:.1%}   of every annotated skill")
    print(f"IN-VOCAB RECALL      {inv_recall:.1%}   of skills the vocabulary contains")
    print(f"FALSE POSITIVES      {sum(false_positives.values())} total, "
          f"{len(false_positives)} distinct terms")
    print("-" * 78)

    if coverage < 0.5:
        print(f"\n*** The vocabulary is the bottleneck: {1 - coverage:.0%} of the skills")
        print(f"*** real recruiters annotate are not in SKILL_VOCAB at all. Growing the")
        print(f"*** list raises recall far more than improving the matcher would.")

    print(f"\nTOP MISSES — in vocabulary, so these are matcher failures ({args.show} max):")
    for skill, n in missed_invocab.most_common(args.show):
        print(f"  {n:>5}x  {skill}")
    if not missed_invocab:
        print("  (none — the matcher found every in-vocabulary skill)")

    print(f"\nTOP MISSES — not in vocabulary, so these are coverage gaps ({args.show} max):")
    for skill, n in missed_outofvocab.most_common(args.show):
        print(f"  {n:>5}x  {skill}")

    print(f"\nTOP FALSE POSITIVES — extracted but not annotated ({args.show} max):")
    print("  (treat with care: annotators miss things too, so some of these are")
    print("   correct extractions the human simply did not mark)")
    for skill, n in false_positives.most_common(args.show):
        print(f"  {n:>5}x  {skill}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
