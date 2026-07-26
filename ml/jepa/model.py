"""A small JEPA-style model for resume / job text.

JEPA = Joint-Embedding Predictive Architecture. Plain English:

    Hide part of a document. Look at what's left (the "context"). Try to predict
    the *embedding* of the hidden part, not its words.

That last bit is the whole point. A language model predicts tokens, so it burns
capacity on grammar and word choice. JEPA predicts a vector, so it only has to
get the *meaning* right — which is exactly what we need for "does this resume
match this job".

Three pieces (this is the standard JEPA recipe):

  1. context encoder  — trainable. Reads the visible text, produces embeddings.
  2. target encoder   — NOT trained by gradients. It is a slow-moving copy of the
                        context encoder (exponential moving average). It produces
                        the embeddings we try to predict.
  3. predictor        — small head: from the context summary + "which span am I
                        being asked about", predict that span's target embedding.

Why the EMA copy instead of just using the same encoder for both sides? Because
then the model can cheat: output the constant zero vector for everything and the
prediction is perfect. That is called representation collapse. A target that
lags behind and gets no gradient removes the shortcut. It is the same trick BYOL
and I-JEPA use.

Sizes here are deliberately small (~5M params) so pretraining fits in a free
Colab/Kaggle GPU session, and a smoke test runs on a laptop CPU.
"""

from __future__ import annotations

import copy
import re
import zlib

import torch
import torch.nn as nn
import torch.nn.functional as F

# ---------------------------------------------------------------------------
# Tokenizer: hashing, no vocab file, no downloads.
# ---------------------------------------------------------------------------
# A real tokenizer needs a vocab file trained on a corpus. We skip that entirely:
# lowercase, split into words, hash each word into a fixed number of buckets.
# Two different rare words can collide into the same bucket — that costs a little
# accuracy and buys zero setup, zero network, and offline smoke tests.
# ponytail: hashing tokenizer, swap in a real BPE tokenizer if collisions hurt eval.

VOCAB_SIZE = 32768
PAD_ID = 0
MASK_ID = 1
_WORD = re.compile(r"[a-z0-9+#.]+")


def tokenize(text: str, max_len: int = 256) -> list[int]:
    """Text -> list of token ids. IDs 0 and 1 are reserved for PAD and MASK."""
    # crc32, not Python's hash(): built-in str hashing is randomised per process,
    # so a checkpoint trained in one run would see different ids in the next.
    words = _WORD.findall(text.lower())[:max_len]
    return [(zlib.crc32(w.encode()) % (VOCAB_SIZE - 2)) + 2 for w in words]


def pad_batch(sequences: list[list[int]], max_len: int) -> torch.Tensor:
    """Stack ragged token lists into one (batch, max_len) tensor, padded with PAD_ID."""
    out = torch.full((len(sequences), max_len), PAD_ID, dtype=torch.long)
    for i, seq in enumerate(sequences):
        seq = seq[:max_len]
        out[i, : len(seq)] = torch.tensor(seq, dtype=torch.long)
    return out


# ---------------------------------------------------------------------------
# Encoder: the thing that turns tokens into vectors.
# ---------------------------------------------------------------------------
class TextEncoder(nn.Module):
    """Embedding table + positional embeddings + a few transformer layers.

    Output is one vector per token. Whoever calls it decides how to pool those
    into a single document vector.
    """

    def __init__(self, dim: int = 256, depth: int = 4, heads: int = 4,
                 max_len: int = 256) -> None:
        super().__init__()
        # one learned vector per vocabulary bucket
        self.token_emb = nn.Embedding(VOCAB_SIZE, dim, padding_idx=PAD_ID)
        # transformers have no built-in sense of word order, so we add a learned
        # "position 0, position 1, ..." vector on top
        self.pos_emb = nn.Embedding(max_len, dim)
        layer = nn.TransformerEncoderLayer(
            d_model=dim,
            nhead=heads,
            dim_feedforward=dim * 4,
            dropout=0.1,
            batch_first=True,   # tensors are (batch, tokens, dim)
            norm_first=True,    # pre-norm: trains more stably at small scale
        )
        self.blocks = nn.TransformerEncoder(layer, num_layers=depth)
        self.norm = nn.LayerNorm(dim)
        self.max_len = max_len

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        """(batch, len) token ids -> (batch, len, dim) contextual embeddings."""
        positions = torch.arange(tokens.size(1), device=tokens.device)
        x = self.token_emb(tokens) + self.pos_emb(positions)[None, :, :]
        # tell attention to ignore padding, otherwise blank slots dilute the meaning
        pad_mask = tokens.eq(PAD_ID)
        x = self.blocks(x, src_key_padding_mask=pad_mask)
        return self.norm(x)


def masked_mean(states: torch.Tensor, keep: torch.Tensor) -> torch.Tensor:
    """Average token vectors where keep is True. (batch, len, dim) -> (batch, dim)."""
    keep = keep.unsqueeze(-1).float()
    return (states * keep).sum(1) / keep.sum(1).clamp(min=1.0)


# ---------------------------------------------------------------------------
# The JEPA wrapper: context encoder + EMA target encoder + predictor.
# ---------------------------------------------------------------------------
class JEPA(nn.Module):
    def __init__(self, dim: int = 256, depth: int = 4, heads: int = 4,
                 max_len: int = 256, ema: float = 0.996) -> None:
        super().__init__()
        self.context_encoder = TextEncoder(dim, depth, heads, max_len)

        # The target encoder starts as an exact copy and is never touched by the
        # optimiser — only by update_target() below.
        self.target_encoder = copy.deepcopy(self.context_encoder)
        for p in self.target_encoder.parameters():
            p.requires_grad = False

        # Predictor: "given what I could see, plus where the hidden span was,
        # what does that span mean?" Two layers is plenty at this scale.
        self.span_pos = nn.Embedding(max_len, dim)  # encodes *where* the span was
        self.predictor = nn.Sequential(
            nn.Linear(dim * 2, dim * 2), nn.GELU(), nn.Linear(dim * 2, dim)
        )
        self.ema = ema

    # --- pretraining path -------------------------------------------------
    def forward(self, tokens: torch.Tensor, span_mask: torch.Tensor
                ) -> tuple[torch.Tensor, torch.Tensor]:
        """One JEPA step.

        tokens:    (batch, len) original, unmasked token ids
        span_mask: (batch, len) True where a span is hidden from the context
        returns:   (predicted span embedding, true span embedding)
        """
        real = tokens.ne(PAD_ID)                 # actual words, not padding
        visible = real & ~span_mask              # what the context encoder may read

        # Context side: replace hidden tokens with MASK, encode, pool the visible part.
        blanked = tokens.masked_fill(span_mask, MASK_ID)
        ctx_states = self.context_encoder(blanked)
        ctx_summary = masked_mean(ctx_states, visible)

        # Target side: encode the ORIGINAL text with the EMA copy, pool only the
        # hidden span. no_grad because gradients must never reach the target.
        with torch.no_grad():
            tgt_states = self.target_encoder(tokens)
            target = masked_mean(tgt_states, span_mask & real)

        # Where was the span? Use the average masked position as a coarse hint,
        # so the predictor knows it is being asked about the start vs the end.
        idx = torch.arange(tokens.size(1), device=tokens.device).float()
        centre = ((span_mask.float() * idx).sum(1) / span_mask.float().sum(1).clamp(min=1))
        pos = self.span_pos(centre.long().clamp(max=self.span_pos.num_embeddings - 1))

        prediction = self.predictor(torch.cat([ctx_summary, pos], dim=-1))
        return prediction, target

    @torch.no_grad()
    def update_target(self) -> None:
        """Nudge the target encoder a tiny step towards the context encoder.

        target = ema * target + (1 - ema) * context, per parameter. With ema=0.996
        the target trails ~250 steps behind — new enough to be useful, old enough
        that the context encoder cannot chase it into a collapsed solution.
        """
        for tgt, ctx in zip(self.target_encoder.parameters(),
                            self.context_encoder.parameters()):
            tgt.mul_(self.ema).add_(ctx, alpha=1 - self.ema)
        for tgt, ctx in zip(self.target_encoder.buffers(),
                            self.context_encoder.buffers()):
            tgt.copy_(ctx)

    # --- inference path ---------------------------------------------------
    @torch.no_grad()
    def embed(self, texts: list[str], max_len: int = 256,
              device: str = "cpu") -> torch.Tensor:
        """Text -> one L2-normalised vector per document.

        This is what downstream scoring uses: cosine similarity between a resume
        vector and a job vector. Uses the target encoder because it is the
        smoothed, more stable of the two.
        """
        self.eval()
        tokens = pad_batch([tokenize(t, max_len) for t in texts], max_len).to(device)
        states = self.target_encoder(tokens)
        pooled = masked_mean(states, tokens.ne(PAD_ID))
        return F.normalize(pooled, dim=-1)


def jepa_loss(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """How wrong was the prediction?

    Cosine distance, not MSE: we care about the *direction* of the embedding
    (that is what cosine similarity scoring reads later), not its length.
    """
    return (1 - F.cosine_similarity(prediction, target, dim=-1)).mean()


def make_span_mask(tokens: torch.Tensor, ratio: float = 0.35,
                   min_span: int = 4) -> torch.Tensor:
    """Pick one contiguous span per document to hide.

    Contiguous, not scattered single words — hiding random individual words is too
    easy to fill in from neighbours, and teaches nothing about meaning.
    """
    batch, length = tokens.shape
    mask = torch.zeros_like(tokens, dtype=torch.bool)
    real_lengths = tokens.ne(PAD_ID).sum(1)
    for i in range(batch):
        n = int(real_lengths[i].item())
        if n < min_span * 2:          # document too short to hide anything useful
            continue
        span = max(min_span, int(n * ratio))
        span = min(span, n - min_span)  # always leave some context visible
        start = int(torch.randint(0, n - span + 1, (1,)).item())
        mask[i, start:start + span] = True
    return mask


def _self_check() -> None:
    """python ml/jepa/model.py — proves shapes line up and EMA actually moves."""
    torch.manual_seed(0)
    m = JEPA(dim=32, depth=1, heads=2, max_len=64, ema=0.9)
    texts = ["python fastapi postgres docker kubernetes backend engineer " * 4,
             "react typescript tailwind frontend accessibility testing " * 4]
    tokens = pad_batch([tokenize(t, 64) for t in texts], 64)
    mask = make_span_mask(tokens)
    assert mask.any(), "nothing got masked"
    assert not mask.all(), "everything got masked"

    pred, tgt = m(tokens, mask)
    assert pred.shape == tgt.shape == (2, 32), (pred.shape, tgt.shape)
    assert not tgt.requires_grad, "target must be detached"

    loss = jepa_loss(pred, tgt)
    assert 0.0 <= loss.item() <= 2.0, loss.item()
    loss.backward()
    assert m.context_encoder.token_emb.weight.grad is not None
    assert m.target_encoder.token_emb.weight.grad is None, "target got a gradient"

    before = m.target_encoder.token_emb.weight.clone()
    with torch.no_grad():
        m.context_encoder.token_emb.weight.add_(1.0)
    m.update_target()
    assert not torch.allclose(before, m.target_encoder.token_emb.weight), "EMA did nothing"

    vecs = m.embed(texts, max_len=64)
    assert vecs.shape == (2, 32)
    assert torch.allclose(vecs.norm(dim=-1), torch.ones(2), atol=1e-5), "not normalised"
    print("model self-check ok "
          f"({sum(p.numel() for p in m.parameters()) / 1e6:.2f}M params at test size)")


if __name__ == "__main__":
    _self_check()
