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

1. ~~BM25/keyword semantic score.~~ Shipped, then superseded.
2. **Now:** SBERT (`all-MiniLM-L6-v2`) cosine blended with the lexical signals —
   45% SBERT / 33% keyword coverage / 22% BM25. Shipped, free, local, no research
   needed, and it required no JEPA at all.
3. **Later, only if earned:** replace the SBERT term with distilled JEPA.

Step 3 happens by changing one function — `_semantic_score()` — to call a JEPA
scorer instead of `_sbert_similarity()`. The other five components, the weights, and the API are
untouched. That is the whole point of keeping the scoring engine componentised.

**The bar for step 3:** JEPA must beat the SBERT that is now live in production,
on a held-out set, measured by
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

# PII scrubbing tests (no pytest needed)
python ml/data/test_scrub.py

# what data sources are wired up, their licences, and which you already have
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

Every record goes through **PII scrubbing** (`ml/data/scrub.py`) and an **OCR
quality filter** before it is written. Neither step is optional or skippable.

**No credentials are stored, read, or automated anywhere in this repo.** Kaggle
and Mendeley downloads are a manual step you do once:

1. Log in to the site in a browser.
2. Download the file yourself from the dataset page.
3. Put it in `data/raw/` at the repo root (git-ignored), named as the table below.
4. Run `python ml/data/prepare.py --list` to confirm it's detected.

### Data inventory

Counts are documents **surviving scrub + quality filter + dedupe**, which is what
actually reaches training. Anything marked *not yet downloaded* is a projection.

| # | Source | File in `data/raw/` | Raw | Kept | Real/synth | Licence |
|---|---|---|---:|---:|---|---|
| 1 | GitHub `noran-mohamed/Resume-Classification-Dataset` | `Resume-Classification-Dataset.csv` | 13,389 | **11,875** ✅ | real | ⚠️ **none stated** — scraped from LiveCareer / Google Images / Bing |
| 2 | Kaggle `snehaanbhawal/resume-dataset` | `resume_dataset.csv` | 2,482 | ~2,400 est. | real | CC0 1.0 per dataset page — heavy overlap with #1, dedupe will cut it |
| 3 | Mendeley `wzzwn37gmd` (CareerCorpus) | `CareerCorpus.xlsx` | 302 | ~300 est. | real | CC BY 4.0 — **attribution required** |
| 4 | Zenodo OpenResume | — | ? | 0 | real | 🔒 access-restricted, request pending — see below |
| 5 | Kaggle `gauravduttakiit/resume-dataset` | `UpdatedResumeDataSet.csv` | 962 | ~700 est. | real | CC0 1.0 per dataset page |
| — | `ml/data/sample.jsonl` | *(checked in)* | 20 | 20 | **synthetic** | ours, hand-written |
| — | Kaggle `ravindrasinghrana/job-description-dataset` | `job_descriptions.csv` | ? | — | real | CC0 1.0 — *job* side, not resumes |
| — | HF `jacob-hugging-face/job-descriptions` | *(auto, `--hf`)* | ? | — | real | unstated on the card — *job* side |
| — | HF `jensjorisdecorte/anonymous-working-histories` | *(auto, `--hf`)* | 2,164 | ~2,000 est. | real | CC BY 4.0 — structured work history, not resume prose |

**Running total against the 50,000-document pretraining target:**

| | Documents | % of target |
|---|---:|---:|
| Downloaded and processed today | **11,875** | 23.8% |
| Plausible with sources 2, 3, 5 added (post-dedupe) | ~14,000–15,000 | ~29% |
| Plus the HF working-histories set | ~16,000–17,000 | ~33% |
| **Gap to 50k** | **~33,000** | — |

There is no public corpus that closes that gap. Everything reachable has been
counted; the remaining 33k has to come from live consented traffic (Phase 0's
consent flow is what makes that legal) or from a source not yet found.

### The licence problem — an open question, not a resolved one

**Source #1 is 88% of the corpus and has no redistribution licence.** It was
scraped from LiveCareer, Google Images and Bing by a third party. LiveCareer's
own terms prohibit bulk extraction. The GitHub repo states no licence at all,
which under default copyright means *no* rights are granted — not "public domain
because it's on GitHub".

This project is intended to be **commercial** (ad-supported, per
`docs/PROJECT_PLAN.md`). That combination is the risk:

- These are **real people's resumes**, published without their consent to this use.
- Training a commercial model on them is a different act from academic research,
  and the usual "research use" hand-waving does not cover it.
- A model's weights are generally not considered a derivative work of its
  training data, but that is unsettled and varies by jurisdiction. It is not a
  position to bet a business on without deciding deliberately.

Options, in rough order of caution:

1. **Don't use #1 at all.** Corpus drops to ~3,400 documents. Pretraining is
   dead until live traffic arrives. Safest, slowest.
2. **Use #1 for research only**, never for weights that ship to users. Keeps the
   experiment alive; means throwing the pretrained model away later.
3. **Use it and accept the risk**, on the argument that it is public, widely
   redistributed, scrubbed, and that weights aren't derivative works.
4. **Ask the repo author** to state a licence. Free to do, might just work.

**This is your call, and it is not made.** Nothing here assumes an answer — the
loader works, and whether you run it on #1 is a decision, not a default. My
recommendation is 4 then 2, because option 3's downside lands after you have
users and revenue, which is the worst possible time to discover it.

Sources #2, #3 and #5 are CC0/CC-BY and carry no such problem — but note #2 is
also LiveCareer-derived, so its CC0 claim is the *uploader's* claim about data
they scraped, which is worth exactly as much as their right to make it.

### OpenResume (source #4) — restricted, do not block on it

<https://zenodo.org/records/14726170> is a Zenodo **restricted** record. Process:

1. Open the record page and click **Request access**.
2. State the purpose — research use, resume-matching model pretraining.
3. The depositor approves manually. Expect days to weeks, and expect terms that
   prohibit redistribution.

No code automates this and none should. The pretraining track does not wait on it.

### Explicitly rejected: the Kaggle Job Recommendation Challenge corpus

The ~70,000-record job-recommendation dataset (Kaggle 2012 / arXiv 1607.07657)
looks like the answer to the volume problem and is not. Its records are
**structured career fields** — salary bands, degree codes, company size, years of
experience — not resume text. JEPA masks spans of *text* and predicts their
embeddings; there is nothing to mask in a salary band. Do not add it.

### PII scrubbing — what it does and what it misses

`ml/data/scrub.py`, proven by `ml/data/test_scrub.py` (14 tests, all passing):

- emails, including OCR-mangled spacing (`maria .santos @ example .org`)
- phone numbers — international, US and Indian formats
- URLs and bare social profile paths
- header-block name lines and address lines (layout heuristic, first 6 lines)

Measured on the 11,875 kept documents:

| | |
|---|---|
| Header name line redacted | **95.9%** of documents |
| Contained an email/phone/URL placeholder after scrubbing | 79.9% |
| Regex-detectable PII surviving | **0** |

That last row is weaker evidence than it looks: it uses the same patterns the
scrubber applied, so it proves the scrubber ran, not that PII is gone. The 4.1%
(≈488 documents) where no header name was found are the ones to worry about —
their names are most likely still in there in some layout the heuristic missed.
And names in body text ("reported to Sarah Klein") survive by design; this is
regex and layout, not NER. spaCy NER lands in Phase 2 and is the point to tighten
this.

**Consequence: the scrubbed corpus is still not safe to redistribute.** It is
safe enough to train on locally. Do not publish `ml/data/corpus.jsonl`.

### OCR noise — measured, and smaller than expected

Filter thresholds (in `scrub.py`, stated not buried): `alpha_ratio ≥ 0.70`,
`broken_word_ratio ≤ 0.12`. Two signals because there are two failure modes —
symbol soup is caught by the first, vowel-stripped fragments (`Wrk Exprnc ;
Rspnsblts`) are mostly letters and only the second catches them.

On the 13,389 real documents:

| Reason dropped | Count | Share |
|---|---:|---:|
| Too short (<120 chars) | 9 | 0.1% |
| Too long (>40,000 chars) | 3 | 0.0% |
| **OCR-rejected** | **3** | **0.02%** |
| Duplicates | 1,499 | 11.2% |
| **Kept** | **11,875** | **88.7%** |

Quality distribution: median `alpha_ratio` 0.941 (p1 = 0.887), median
`broken_word_ratio` 0.007 (p99 = 0.045, max 0.104). Tightening to
`alpha ≥ 0.85` would drop 16 documents; `broken ≤ 0.05` would drop 73.

So: **this corpus is not meaningfully OCR-corrupted.** Despite the "OCR-extracted"
label it is mostly clean text extraction, and the quality filter is insurance
against a future dirtier source rather than something doing real work today. The
11.2% duplicate rate is the far larger effect — the same resumes appear on
multiple scraped sites.

Adding a source is one dict in `MANUAL_SOURCES` or `HF_SOURCES`.

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

### Verdict: is a pretraining run worth doing now?

**No — with one exception. The track stays parked.**

We have 11,875 scrubbed real documents, ~16k if every remaining public source is
added. The table above says signal starts around 50k–100k and *"below ~10k the
model memorises"*. 16k is not comfortably past that line; it is just over it, on
a corpus with 11% near-duplicates and one dominant source. A run at this scale
produces a checkpoint that memorises LiveCareer resume boilerplate and loses to
`all-MiniLM-L6-v2` — which is the honest prediction, and `ml/eval.py` would print
`VERDICT: JEPA LOSES` after however many GPU-hours it took.

Three reasons parking is the right call, beyond the count:

1. **The gap is structural, not a to-do.** Every reachable public corpus is
   counted; there is no download that closes 33,000 documents. Consented live
   traffic is the only path, and the Phase 0 consent flow that makes it legal has
   just shipped with zero users behind it.
2. **The licence question is unanswered**, and 88% of the corpus depends on it.
   Training weights on source #1 before deciding means potentially discarding the
   result.
3. **Pretraining is the wrong stage to be optimising.** Per §2, distillation is
   where JEPA can actually beat SBERT, because it learns this product's notion of
   a good match. Pretraining only supplies a domain-adapted starting point. Doing
   it now, badly, on data that may have to be thrown away, buys nothing that
   doing it later on 50k+ documents would not buy better.

**The exception, and it is worth doing:** one short run — 2–3 epochs on the
11,875 documents, an hour of free Kaggle GPU — purely as an infrastructure test.
Not to get a good model. To prove that the loss goes down on real data rather
than on 20 fake records, that the EMA target does not collapse at real scale,
that a checkpoint round-trips, and that `ml/eval.py` runs end to end against it.
Then write down the number it loses by and stop. That is a pipeline test with a
number attached, and it is cheap; a serious pretraining run is not, and should
wait for the data.

**Reassess when:** the corpus passes ~50k documents, *or* consented distillation
triples reach ~5k (§8's minimum) — whichever comes first. The second will
probably arrive before the first, and it is the more valuable of the two.

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
    prepare.py         normalise public corpora into one JSONL (scrub + filter)
    scrub.py           PII redaction + OCR quality signals — mandatory, not optional
    test_scrub.py      14 tests proving scrubbing works on synthetic PII
    sample.jsonl       20 fake records, checked in, zero-download runnability
    sample_pairs.csv   24 fake (resume, job, score) pairs for eval plumbing
    corpus.jsonl       generated, git-ignored, DO NOT redistribute
  jepa/
    model.py           context encoder + EMA target encoder + predictor
    train_pretrain.py  stage 1: self-supervised pretraining
```
