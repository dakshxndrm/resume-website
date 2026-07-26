"""Held-out comparison: JEPA vs the sentence-transformers baseline.

Splits the pairs into a calibration half and a held-out half, fits the
similarity -> 0-100 mapping on the first, and reports Spearman + MAE on the
second for both models. Ends with a one-line verdict.

    python ml/eval.py --checkpoint ml/checkpoints/jepa.pt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from baseline import (DEFAULT_DATA, DEFAULT_PAIRS, calibrate, cosine,  # noqa: E402
                      embed_baseline, load_pairs, report)
from jepa.model import JEPA  # noqa: E402


def load_jepa(path: Path, device: str) -> JEPA:
    checkpoint = torch.load(path, map_location=device, weights_only=False)
    model = JEPA(**checkpoint["config"]).to(device)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model


def jepa_similarities(model: JEPA, resumes: list[str], jobs: list[str],
                      max_len: int, device: str) -> np.ndarray:
    r = model.embed(resumes, max_len, device).cpu().numpy()
    j = model.embed(jobs, max_len, device).cpu().numpy()
    return cosine(r, j)


def split(n: int, holdout: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Deterministic shuffle-split so reruns are comparable."""
    order = np.random.default_rng(seed).permutation(n)
    cut = max(1, int(n * (1 - holdout)))
    return order[:cut], order[cut:]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--checkpoint", default="ml/checkpoints/jepa.pt")
    ap.add_argument("--data", default=str(DEFAULT_DATA))
    ap.add_argument("--pairs", default=str(DEFAULT_PAIRS))
    ap.add_argument("--model", default="all-MiniLM-L6-v2", help="baseline SBERT model")
    ap.add_argument("--holdout", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    checkpoint = Path(args.checkpoint)
    if not checkpoint.exists():
        raise SystemExit(f"no checkpoint at {checkpoint} - run ml/jepa/train_pretrain.py first")

    resumes, jobs, scores = load_pairs(Path(args.data), Path(args.pairs))
    fit_idx, test_idx = split(len(scores), args.holdout, args.seed)
    print(f"{len(scores)} pairs -> {len(fit_idx)} calibration / {len(test_idx)} held out\n")

    model = load_jepa(checkpoint, args.device)
    max_len = model.context_encoder.max_len

    sims = {
        "SBERT baseline": cosine(embed_baseline(resumes, args.model),
                                 embed_baseline(jobs, args.model)),
        "JEPA": jepa_similarities(model, resumes, jobs, max_len, args.device),
    }

    results = {}
    for name, s in sims.items():
        fit = calibrate(s[fit_idx], scores[fit_idx])
        results[name] = report(name, s[test_idx], scores[test_idx], fit)

    base, jepa = results["SBERT baseline"], results["JEPA"]
    d_rho = jepa["spearman"] - base["spearman"]
    d_mae = base["mae"] - jepa["mae"]   # positive = JEPA has lower error
    print()
    if d_rho > 0 and d_mae > 0:
        print(f"VERDICT: JEPA BEATS the baseline (spearman {d_rho:+.3f}, MAE {d_mae:+.1f} pts).")
    elif d_rho > 0 or d_mae > 0:
        print(f"VERDICT: MIXED - spearman {d_rho:+.3f}, MAE {d_mae:+.1f} pts. Not a win yet.")
    else:
        print(f"VERDICT: JEPA LOSES to the baseline (spearman {d_rho:+.3f}, "
              f"MAE {d_mae:+.1f} pts). Keep SBERT in production.")
    if len(test_idx) < 200:
        print(f"CAVEAT: only {len(test_idx)} held-out pairs - this verdict is noise, "
              "not evidence. See ml/README.md on how much data is actually needed.")


if __name__ == "__main__":
    main()
