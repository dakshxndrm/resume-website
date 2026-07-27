"""Score every golden example with the live scorer and report how well it agrees
with the human labels.

    cd backend && python eval/run_benchmark.py
    python eval/run_benchmark.py --dataset eval/golden/dataset.jsonl --verbose

Reads app/services/scoring.py as-is. This file never tunes it and never should:
a benchmark that can be adjusted until it passes measures nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.parsing import _DEGREE_RE, _count_section_entries, extract_skills, split_sections  # noqa: E402
from app.services.scoring import score_resume  # noqa: E402

DEFAULT_DATASET = Path(__file__).resolve().parent / "golden" / "dataset.jsonl"

# --- PASS/FAIL thresholds -------------------------------------------------
# Chosen as "obviously broken vs not obviously broken", not as quality targets.
# Human labelers typically agree with each other at Spearman 0.7-0.8, so 0.6 is
# a floor for usefulness, not a goal.
MIN_SPEARMAN = 0.60      # rank agreement with the human ordering
MAX_MAE = 20.0           # points, on the 0-100 scale, after rescaling labels
MAX_BAND_SHARE = 0.60    # >60% of scores inside any 15-point band = not discriminating
BAND_WIDTH = 15


def resume_dict(text: str) -> dict:
    """Build the dict the scorer expects from plain text.

    Mirrors the tail of parsing.parse_resume(); it is not reused only because that
    function takes file bytes and there is no text entry point.
    ponytail: delete this in favour of parse_resume the day it accepts text.
    """
    sections = split_sections(text)
    edu_section = sections.get("education")
    edu_count = (len(_DEGREE_RE.findall(edu_section)) if edu_section else 0) or \
        _count_section_entries(edu_section)
    return {
        "raw_text": text,
        "skills": extract_skills(text),
        "work": [{"i": i} for i in range(_count_section_entries(sections.get("experience")))],
        "education": [{"i": i} for i in range(edu_count)],
        "projects": [{"i": i} for i in range(_count_section_entries(sections.get("projects")))],
        "word_count": len(text.split()),
    }


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    for row in rows:
        missing = {"id", "human_score", "job_description", "resume_text"} - set(row)
        if missing:
            raise SystemExit(f"{row.get('id', '?')} is missing {sorted(missing)}")
        if not 1 <= row["human_score"] <= 10:
            raise SystemExit(f"{row['id']}: human_score must be 1-10")
    return rows


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    from scipy.stats import spearmanr
    return float(spearmanr(a, b).statistic)


def pearson(a: np.ndarray, b: np.ndarray) -> float:
    from scipy.stats import pearsonr
    return float(pearsonr(a, b).statistic)


def histogram(scores: np.ndarray, width: int = 10) -> str:
    """Text histogram in 10-point buckets."""
    lines = []
    for low in range(0, 100, width):
        count = int(((scores >= low) & (scores < low + width)).sum())
        if low + width == 100:  # last bucket is closed, so a perfect 100 lands somewhere
            count = int(((scores >= low) & (scores <= 100)).sum())
        lines.append(f"  {low:3d}-{low + width - 1:3d} |{'#' * count}{'' if count else ''} {count}")
    return "\n".join(lines)


def worst_band(scores: np.ndarray, width: int = BAND_WIDTH) -> tuple[int, float]:
    """The `width`-point band holding the largest share of scores.

    A scorer that puts everything inside a 15-point window is not discriminating
    between resumes, no matter what its correlation says.
    """
    best_low, best_share = 0, 0.0
    for low in range(0, 101 - width):
        share = float(((scores >= low) & (scores <= low + width)).mean())
        if share > best_share:
            best_low, best_share = low, share
    return best_low, best_share


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default=str(DEFAULT_DATASET))
    ap.add_argument("--verbose", action="store_true", help="print every example")
    args = ap.parse_args()

    rows = load(Path(args.dataset))
    human = np.array([r["human_score"] for r in rows], dtype=float)
    machine = np.array(
        [score_resume(resume_dict(r["resume_text"]), r["job_description"])["total"]
         for r in rows], dtype=float)

    # human 1-10 -> 0-100 so MAE is in the same units as the score the user sees.
    # Linear: 1 -> 0, 10 -> 100. Deliberately not a fitted mapping - fitting the
    # scale would hide a systematic bias, which is exactly what MAE should expose.
    human_100 = (human - 1) / 9 * 100

    print(f"golden set: {len(rows)} examples from {Path(args.dataset).name}\n")

    if args.verbose or True:
        print(f"  {'id':<6} {'human':>5} {'->0-100':>7} {'scorer':>6} {'err':>6}")
        for row, h, h100, m in sorted(zip(rows, human, human_100, machine),
                                      key=lambda t: -t[1]):
            print(f"  {row['id']:<6} {h:5.0f} {h100:7.1f} {m:6.0f} {m - h100:+6.1f}")
        print()

    rho, r = spearman(machine, human), pearson(machine, human)
    mae = float(np.abs(machine - human_100).mean())
    bias = float((machine - human_100).mean())
    low, share = worst_band(machine)

    print(f"Spearman (rank agreement) : {rho:+.3f}   threshold >= {MIN_SPEARMAN:.2f}")
    print(f"Pearson  (linear)         : {r:+.3f}")
    print(f"MAE vs rescaled labels    : {mae:5.1f} pts   threshold <= {MAX_MAE:.0f}")
    print(f"Mean signed error (bias)  : {bias:+5.1f} pts   "
          f"({'scorer runs high' if bias > 0 else 'scorer runs low'})")
    print(f"Score range               : {machine.min():.0f} - {machine.max():.0f}\n")

    print("Score distribution (10-point buckets):")
    print(histogram(machine))
    print(f"\nTightest {BAND_WIDTH}-point band: {low}-{low + BAND_WIDTH} holds "
          f"{share:.0%} of scores   threshold < {MAX_BAND_SHARE:.0%}")
    if share > MAX_BAND_SHARE:
        print(f"  FLAG: over {MAX_BAND_SHARE:.0%} of scores sit in a {BAND_WIDTH}-point "
              "band - the scorer is barely separating these resumes.")

    failures = []
    if rho < MIN_SPEARMAN:
        failures.append(f"Spearman {rho:+.3f} < {MIN_SPEARMAN:.2f}")
    if mae > MAX_MAE:
        failures.append(f"MAE {mae:.1f} > {MAX_MAE:.0f}")
    if share > MAX_BAND_SHARE:
        failures.append(f"{share:.0%} of scores in a {BAND_WIDTH}-point band "
                        f"> {MAX_BAND_SHARE:.0%}")

    print()
    if failures:
        print("VERDICT: FAIL - " + "; ".join(failures))
    else:
        print(f"VERDICT: PASS - Spearman {rho:+.3f} >= {MIN_SPEARMAN:.2f}, "
              f"MAE {mae:.1f} <= {MAX_MAE:.0f}, "
              f"tightest band {share:.0%} < {MAX_BAND_SHARE:.0%}")
    print(f"CAVEAT: {len(rows)} synthetic examples. This detects gross failures only - "
          "see eval/README.md before quoting any of these numbers.")

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
