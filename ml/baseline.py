"""The yardstick JEPA has to beat: off-the-shelf sentence-transformers.

all-MiniLM-L6-v2 is free, runs on CPU, and is already good at this. If JEPA does
not beat these numbers on a held-out set, JEPA is not worth shipping - use SBERT
and move on. That is the honest framing; see ml/README.md.

    python ml/baseline.py                       # sample data
    python ml/baseline.py --pairs mypairs.csv --data mycorpus.jsonl

Inputs:
  --data   JSONL, one {"text": ..., "type": ...} per line (line number = id)
  --pairs  CSV with columns resume_id, job_id, score  (score = ground truth 0-100)
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_DATA = HERE / "data" / "sample.jsonl"
DEFAULT_PAIRS = HERE / "data" / "sample_pairs.csv"


def load_pairs(data_path: Path, pairs_path: Path
               ) -> tuple[list[str], list[str], np.ndarray]:
    """Resolve (resume_id, job_id, score) rows into actual text pairs."""
    with Path(data_path).open(encoding="utf-8") as fh:
        docs = [json.loads(line)["text"] for line in fh if line.strip()]

    resumes, jobs, scores = [], [], []
    with Path(pairs_path).open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            resumes.append(docs[int(row["resume_id"])])
            jobs.append(docs[int(row["job_id"])])
            scores.append(float(row["score"]))
    if not resumes:
        raise SystemExit(f"no pairs in {pairs_path}")
    return resumes, jobs, np.asarray(scores, dtype=float)


def cosine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Row-wise cosine similarity between two (n, dim) matrices."""
    a = a / np.linalg.norm(a, axis=1, keepdims=True).clip(min=1e-9)
    b = b / np.linalg.norm(b, axis=1, keepdims=True).clip(min=1e-9)
    return (a * b).sum(axis=1)


def embed_baseline(texts: list[str], model_name: str = "all-MiniLM-L6-v2") -> np.ndarray:
    """Encode with sentence-transformers. Downloads the model once (~90MB)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name).encode(texts, convert_to_numpy=True,
                                                  show_progress_bar=False)


def calibrate(similarities: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    """Least-squares fit of similarity -> 0-100 score.

    Cosine similarity lives on its own arbitrary scale, so comparing it to a
    0-100 label directly would make MAE meaningless. Fit slope/intercept on a
    training split, then measure error on data the fit never saw.
    """
    slope, intercept = np.polyfit(similarities, scores, 1)
    return float(slope), float(intercept)


def report(name: str, similarities: np.ndarray, scores: np.ndarray,
           fit: tuple[float, float] | None = None) -> dict[str, float]:
    """Spearman correlation (rank agreement) + MAE on the 0-100 scale."""
    from scipy.stats import spearmanr

    rho = float(spearmanr(similarities, scores).statistic)
    slope, intercept = fit if fit else calibrate(similarities, scores)
    predicted = slope * similarities + intercept
    mae = float(np.abs(predicted - scores).mean())
    print(f"{name:<26} spearman {rho:+.3f}   MAE {mae:5.1f} pts   n={len(scores)}")
    return {"spearman": rho, "mae": mae}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(DEFAULT_DATA))
    ap.add_argument("--pairs", default=str(DEFAULT_PAIRS))
    ap.add_argument("--model", default="all-MiniLM-L6-v2")
    args = ap.parse_args()

    resumes, jobs, scores = load_pairs(Path(args.data), Path(args.pairs))
    print(f"{len(scores)} pairs from {Path(args.pairs).name}, encoding with {args.model} ...")
    similarities = cosine(embed_baseline(resumes, args.model),
                          embed_baseline(jobs, args.model))

    report(f"SBERT {args.model}", similarities, scores)
    print("\nNote: fit and evaluated on the same pairs (no held-out split here) - "
          "this is the in-sample ceiling for the baseline.\n"
          "Use ml/eval.py for the held-out comparison against JEPA.")


if __name__ == "__main__":
    main()
