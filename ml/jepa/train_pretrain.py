"""Stage 1: self-supervised JEPA pretraining. No labels required.

For each document: hide a span, ask the model to predict that span's embedding
(see ml/jepa/model.py for what that means and why).

    # prove the pipeline runs end to end, 2 steps, CPU, sample data:
    python ml/jepa/train_pretrain.py --smoke-test

    # a real run (Colab/Kaggle GPU):
    python ml/jepa/train_pretrain.py --data ml/data/corpus.jsonl --epochs 20 --batch 32
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jepa.model import JEPA, jepa_loss, make_span_mask, pad_batch, tokenize  # noqa: E402

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample.jsonl"


class JsonlText(Dataset):
    """Reads {"text": ...} lines and hands back token id lists."""

    def __init__(self, path: Path, max_len: int, kinds: set[str] | None = None) -> None:
        self.max_len = max_len
        self.items: list[list[int]] = []
        with Path(path).open(encoding="utf-8") as fh:
            for line in fh:
                record = json.loads(line)
                if kinds and record.get("type") not in kinds:
                    continue
                ids = tokenize(record["text"], max_len)
                if len(ids) >= 16:   # too short to hide a meaningful span
                    self.items.append(ids)
        if not self.items:
            raise SystemExit(f"no usable documents in {path}")

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int) -> list[int]:
        return self.items[i]


def collate(batch: list[list[int]], max_len: int) -> torch.Tensor:
    return pad_batch(batch, max_len)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(SAMPLE), help="JSONL corpus from ml/data/prepare.py")
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--dim", type=int, default=256)
    ap.add_argument("--depth", type=int, default=4)
    ap.add_argument("--heads", type=int, default=4)
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--mask-ratio", type=float, default=0.35)
    ap.add_argument("--ema", type=float, default=0.996)
    ap.add_argument("--out", default="ml/checkpoints/jepa.pt")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--smoke-test", action="store_true",
                    help="2 steps on the sample data, tiny model, CPU - pipeline check only")
    args = ap.parse_args()

    if args.smoke_test:
        # Small enough that this finishes in seconds on a laptop with no GPU.
        args.data, args.device = str(SAMPLE), "cpu"
        args.epochs, args.batch, args.max_len = 1, 2, 64
        args.dim, args.depth, args.heads = 64, 2, 2
        args.out = "ml/checkpoints/smoke.pt"

    torch.manual_seed(args.seed)

    dataset = JsonlText(Path(args.data), args.max_len)
    loader = DataLoader(dataset, batch_size=args.batch, shuffle=True, drop_last=False,
                        collate_fn=lambda b: collate(b, args.max_len))

    model = JEPA(args.dim, args.depth, args.heads, args.max_len, args.ema).to(args.device)
    optimiser = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=args.lr, weight_decay=0.01
    )
    params = sum(p.numel() for p in model.context_encoder.parameters())
    print(f"{len(dataset)} docs | {params / 1e6:.1f}M trainable params | device={args.device}")

    max_steps = 2 if args.smoke_test else None
    step, started = 0, time.time()
    for epoch in range(args.epochs):
        model.train()
        running = 0.0
        for batch_i, tokens in enumerate(loader, start=1):
            tokens = tokens.to(args.device)
            span_mask = make_span_mask(tokens, args.mask_ratio)
            if not span_mask.any():
                continue  # whole batch was too short; nothing to learn from

            prediction, target = model(tokens, span_mask)
            loss = jepa_loss(prediction, target)

            optimiser.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimiser.step()
            model.update_target()   # EMA nudge - must happen after every step

            running += loss.item()
            step += 1
            if max_steps and step >= max_steps:
                print(f"step {step} loss {loss.item():.4f}")
                break
            if step % 50 == 0:
                print(f"epoch {epoch + 1} step {step} loss {running / batch_i:.4f}")
        else:
            print(f"epoch {epoch + 1}/{args.epochs} loss {running / max(1, len(loader)):.4f}")
            save(model, args, epoch + 1)
            continue
        break  # smoke test hit its step cap

    save(model, args, args.epochs)
    print(f"done: {step} steps in {time.time() - started:.1f}s -> {args.out}")
    if args.smoke_test:
        print("SMOKE TEST PASSED - pipeline runs end to end. "
              "This model has learned nothing useful; see ml/README.md on data volume.")


def save(model: JEPA, args: argparse.Namespace, epoch: int) -> None:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(),
                "config": {"dim": args.dim, "depth": args.depth, "heads": args.heads,
                           "max_len": args.max_len, "ema": args.ema},
                "epoch": epoch}, out)


if __name__ == "__main__":
    main()
