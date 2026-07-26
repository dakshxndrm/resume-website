# ml/ — the JEPA research track (Phase 3)

This folder is a **background research track**. Nothing here is imported by the
website. `backend/` and `frontend/` do not depend on a single file in `ml/`, and
they must not start depending on one until the numbers in `ml/eval.py` say so.

It has its own `requirements.txt` and its own virtualenv on purpose — the API
server should never be forced to install PyTorch.

---

## 1. What is JEPA, in plain language

JEPA stands for **Joint-Embedding Predictive Architecture**. It is a way of
training a model without labels. The idea in one sentence:

> Hide part of a document, look at what's left, and try to predict the
> **embedding** (the meaning-vector) of the hidden part — not its words.

Compare that to how a language model like GPT trains: it predicts the *next
word*. To do that well it has to model grammar, spelling, style, and word
choice. Most of that effort is wasted if all you want is "how well does this
resume match this job".

JEPA predicts a vector instead. It never has to get the exact wording right — it
only has to get the *meaning* right. That makes it much smaller and cheaper to
train, which is the entire reason it's viable for a solo, $0-budget project.

### What it does here — and what it does not

**It does:** turn a resume into a vector, turn a job description into a vector,
and score the match as the cosine similarity between them. One number, 0–100,
computed locally in milliseconds, no API call, no quota, no per-request cost.

**It does not write text.** It cannot generate a suggestion, rewrite a bullet
point, or explain anything. Ever. That is not what this kind of model is. The
LLM (Gemini/Groq) keeps doing all the writing, permanently — see
`docs/PROJECT_PLAN.md` §1.

### The three pieces

Every JEPA has these, and `ml/jepa/model.py` implements all three:

| Piece | What it does |
|---|---|
| **Context encoder** | Reads the visible text. This is the part that actually learns. |
| **Target encoder** | Produces the "right answer" embeddings. It is a slow-moving *copy* of the context encoder (an exponential moving average), and gradients never reach it. |
| **Predictor** | Small head: given the context, predict the hidden span's target embedding. |

Why the frozen EMA copy? Without it the model has a trivial cheat available:
output the same constant vector for every input, and the prediction is always
perfect while the model has learned nothing. That failure is called
**representation collapse**, and a lagging, gradient-free target is the standard
defence (same trick BYOL and Meta's I-JEPA use).

---

## 2. The two training stages

### Stage 1 — self-supervised pretraining (`ml/jepa/train_pretrain.py`)

Train on public resume and job-description corpora with **no labels at all**.
Mask a span, predict its embedding, repeat. The model comes out of this knowing
something about the shape of resume/job language — that "FastAPI" and "Django"
live near each other, that a skills list looks different from an education
section. It does **not** come out knowing what a good match is.

Status: **implemented and runnable.** Quality: unproven.

### Stage 2 — distillation from the LLM teacher (Phase 4, not built yet)

Once the site is live, every consented resume that the LLM scores becomes a
training pair: `(resume, job) -> the LLM's score`. JEPA is then fine-tuned to
reproduce those scores. This is textbook **knowledge distillation** — teacher =
LLM, student = JEPA.

This stage is what actually makes JEPA useful, and it cannot start before the
site has real traffic. Nothing for it exists in this folder yet.

Status: **aspirational.** No code, no data.

---

## 3. How this eventually reaches the live site

`backend/app/services/scoring.py` computes six weighted components. One of them
is **semantic, worth 20%**. Today `_semantic_score()` is BM25 + keyword
coverage — real, local, free, and honestly a bit crude.

The swap path, in order, is:

1. **Now:** BM25/keyword semantic score. Shipped.
2. **Next:** replace it with sentence-transformers (SBERT) cosine similarity —
   better than BM25, still free and local, no research needed. This is the
   sensible upgrade and it does not require JEPA at all.
3. **Later, only if earned:** replace SBERT with distilled JEPA.

Step 3 happens by changing exactly one function — `_semantic_score()` — to call
a JEPA scorer. The other five components, the weights, and the API are
untouched. That is the whole point of keeping the scoring engine componentised.

**The bar for step 3:** JEPA must beat SBERT on a held-out set, measured by
`ml/eval.py`, on real data at real scale. Until `ml/eval.py` prints
`VERDICT: JEPA BEATS the baseline` on a few hundred genuine pairs, JEPA stays in
this folder. Losing to a model you can `pip install` in thirty seconds is the
expected outcome for a long time, and that is fine — this track is a bet, not a
plan.

---

## 4. Real vs aspirational — no ambiguity

| Thing | Status |
|---|---|
| JEPA architecture (`jepa/model.py`) | **Real.** Runs, self-checks, ~5M params. |
| Pretraining loop (`jepa/train_pretrain.py`) | **Real.** Smoke test passes on CPU. |
| SBERT baseline (`baseline.py`) | **Real.** This is a genuinely good model. |
| Held-out evaluation (`eval.py`) | **Real** as code. Meaningless on sample data. |
| Sample data (20 fake records, 24 fake pairs) | **Real files, fake content.** Written by hand to make the scripts runnable offline. The scores in `sample_pairs.csv` are my guesses, not human labels. |
| Public corpora ingestion (`data/prepare.py`) | **Real code, nothing downloaded yet.** |
| JEPA beating SBERT | **Aspirational.** Has not happened. May never happen. |
| Distillation from the LLM | **Aspirational.** Not built. Needs live traffic. |
| JEPA in production scoring | **Aspirational.** `backend/` does not know this folder exists. |

---

## 5. Setup

### Windows, CPU-only

```bat
python -m venv ml\venv
ml\venv\Scripts\activate
pip install torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r ml\requirements.txt
```

Install torch from the CPU index **first**. Skip that and pip pulls the ~2.5GB
CUDA build, which is useless on a machine without an NVIDIA GPU.

### Colab / Kaggle (free GPU, this is where real training happens)

torch and numpy are preinstalled with working CUDA. **Do not reinstall torch** —
it will downgrade the GPU build. Just:

```python
!pip install -q sentence-transformers==3.1.1 datasets==2.21.0
```

Kaggle gives ~30 GPU-hours/week, Colab a few hours a session. Both are enough
for a model this size. Checkpoint to Drive or Kaggle output — sessions die
without warning.

---

## 6. Running things

```bash
# prove the whole pipeline works, 2 steps, CPU, no downloads, ~10 seconds
python ml/jepa/train_pretrain.py --smoke-test

# the baseline you must beat
python ml/baseline.py

# held-out comparison + verdict (needs a checkpoint)
python ml/eval.py --checkpoint ml/checkpoints/jepa.pt

# what data sources are wired up, and which you already have
python ml/data/prepare.py --list

# build a real corpus once datasets are in data/raw/
python ml/data/prepare.py --hf --out ml/data/corpus.jsonl

# component self-checks
python ml/jepa/model.py
python ml/data/prepare.py --self-check
```

A real pretraining run:

```bash
python ml/jepa/train_pretrain.py --data ml/data/corpus.jsonl \
    --epochs 20 --batch 32 --lr 3e-4
```

---

## 7. Getting real data

`ml/data/prepare.py` normalises everything into one JSONL file:

```json
{"text": "...", "type": "resume"}
{"text": "...", "type": "job"}
```

**No credentials are stored, read, or automated anywhere in this repo.** Kaggle
downloads are a manual step you do once:

1. Log in to Kaggle in a browser.
2. Download the dataset zip yourself from the dataset page.
3. Unzip the CSV into `data/raw/` at the repo root (git-ignored).
4. Run `python ml/data/prepare.py --list` to confirm it's detected.

Sources currently wired up (`--list` shows which are present):

| File in `data/raw/` | Source | Kind |
|---|---|---|
| `resume_dataset.csv` | Kaggle `snehaanbhawal/resume-dataset` (~2.4k resumes) | resume |
| `UpdatedResumeDataSet.csv` | Kaggle `gauravduttakiit/resume-dataset` (~1k resumes) | resume |
| `job_descriptions.csv` | Kaggle `ravindrasinghrana/job-description-dataset` | job |
| *(auto, `--hf`)* | Hugging Face `jacob-hugging-face/job-descriptions` — public, no login | job |

Adding a source is one dict in `MANUAL_SOURCES` or `HF_SOURCES`.

Check each dataset's licence before using it, and note that public resume
corpora are usually scraped — treat them as pretraining fodder, not as labelled
ground truth.

---

## 8. How much data does this actually need?

Honest numbers, so nobody gets excited about a smoke test:

| Stage | Realistic requirement |
|---|---|
| Smoke test | 20 fake docs. Proves plumbing, proves nothing else. |
| Pretraining showing *any* signal | ~50k–100k documents. Below ~10k the model memorises. |
| Pretraining competitive with SBERT | ~500k+ documents. SBERT was trained on **1 billion** sentence pairs — that is the gap being closed from scratch. |
| Distillation (the stage that actually matters) | ~5k–10k real `(resume, job, LLM score)` triples minimum; 50k+ to be comfortable. |
| A trustworthy eval verdict | 200+ held-out pairs with consistent scoring, absolute floor. Below that the confidence interval is wider than any difference being measured. |

The realistic path is **not** "beat SBERT from scratch" — that is a losing race
against a billion training pairs. It is: pretrain on public corpora to get a
domain-adapted starting point, then distil the LLM's judgments into it. The
distillation stage is where JEPA can genuinely win, because it learns *this
product's* notion of a good match, which SBERT has never seen.

---

## 9. Layout

```
ml/
  README.md            this file
  requirements.txt     CPU-only install notes for Windows + Colab/Kaggle
  .gitignore           datasets, checkpoints, venv never reach GitHub
  baseline.py          sentence-transformers benchmark — the bar to beat
  eval.py              held-out JEPA vs baseline, prints a verdict
  data/
    prepare.py         normalise public corpora into one JSONL
    sample.jsonl       20 fake records, checked in, zero-download runnability
    sample_pairs.csv   24 fake (resume, job, score) pairs for eval plumbing
  jepa/
    model.py           context encoder + EMA target encoder + predictor
    train_pretrain.py  stage 1: self-supervised pretraining
```
