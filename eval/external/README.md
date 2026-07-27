# External dataset benchmarks

Measurement only. Nothing in `eval/` modifies `app/` — the scorer is imported and
called exactly as production calls it, never monkeypatched or reweighted.

Every download is manual. No script here logs in, scrapes, or accepts credentials.
All downloads land in `eval/external/data/`, which is gitignored.

```bash
mkdir -p eval/external/data
cd eval/external

# no download needed — run this one first
../../backend/.venv/Scripts/python stress_intervals.py

../../backend/.venv/Scripts/python careercorpus.py   --file data/careercorpus.xlsx
../../backend/.venv/Scripts/python parsing_check.py  --file data/resume-corpus.json
```

Use the backend venv — these scripts import `app.services.*`. Extra dependency for
CareerCorpus only: `backend/.venv/Scripts/pip install openpyxl`. `scipy` is already
present (it ships with sentence-transformers) and supplies the correlations.

Set `SBERT_DISABLED=1` to measure the lexical-only path. Every script prints which
semantic mode it ran in — a result quoted without that line is not reproducible.

---

## 1. CareerCorpus — 302 resumes, dual expert annotation

**Download:** https://data.mendeley.com/datasets/wzzwn37gmd/1 → save the `.xlsx` as
`data/careercorpus.xlsx`. Licence **CC-BY-4.0** (redistribution permitted with
attribution; still gitignored here to keep the repo lean).

302 resumes across six occupational categories, each scored independently by two
domain experts.

### What it CAN validate
Whether the scorer's **quality ranking** agrees with expert human judgement, and
whether that agreement holds across occupations rather than only in software.

### What it CANNOT validate
- **Job matching — at all.** The dataset contains **no job descriptions**. Every
  resume is scored with `job_description=None`, which makes the semantic component
  return its neutral constant for all 302 rows. That component carries 20% of the
  total weight and contributes **zero variance** here, so any correlation is a
  verdict on the other 80% only. The single largest thing this product claims to do
  is untested by this dataset.
- **The full quality range.** These resumes come from LiveCareer and are
  professionally crafted, so genuine quality varies far less than in real applicant
  traffic. Both a compressed output distribution and an artificially low correlation
  are expected consequences of range restriction, and this dataset cannot separate
  "the scorer can't discriminate" from "there was nothing to discriminate".

### The ceiling — read every result against this
Published inter-annotator agreement:

| Category | Agreement |
|---|---|
| Apparel | 0.89 |
| Finance | 0.68 |
| Research Assistant | 0.67 |
| Teacher | 0.56 |
| Banking | 0.38 |
| Accountant | 0.35 |

Two paid domain experts looking at the same Accountant resume agreed **0.35**. A
scorer reaching 0.35 there has matched human performance; demanding 0.8 is demanding
that a heuristic be more consistent than the humans who defined the target. The
script prints this table before it prints any result, and phrases each verdict as
`observed vs ceiling`.

Column names are auto-detected and echoed back; override with `--text-col`,
`--score-cols A B`, `--category-col` if the dataset version differs.

---

## 2. Kaggle — snehaanbhawal/resume-dataset — 2,482 resumes, 24 industries

**Download:** https://www.kaggle.com/datasets/snehaanbhawal/resume-dataset —
requires a free Kaggle account. Sign in **in your browser** and download manually,
or use your own configured `kaggle` CLI credentials. No script here will do it.
Save to `data/kaggle-resumes/`. Licence: check the dataset page — CC0 at time of
writing, verify before redistributing.

### What it CAN validate
Scale and **category separation**: 2,482 resumes across 24 industries is enough to
check that the score distribution isn't collapsed, and to cross-score every industry
against every other industry's postings — a resume should score higher against its
own industry than against the other 23. That is a real job-matching signal and the
only dataset here big enough to produce it.

### What it CANNOT validate
**Quality.** There are no quality labels of any kind — only an industry label. It
can tell you the scorer discriminates *between* industries; it cannot tell you
whether it ranks two accountants correctly. Also no job descriptions ship with it;
the cross-industry test requires synthesising postings per industry, which measures
against your own synthetic text, not against real hiring language.

No script is provided for this dataset yet — it is documented here because it is the
right next step once the two below are green.

---

## 3. Resume-Corpus-Dataset — NER, 36 entity types

**Download:** https://github.com/vrundag91/Resume-Corpus-Dataset — clone or download
the annotation dump to `data/resume-corpus.json`. Check the repo for its licence
before redistributing; it is a research corpus.

### What it CAN validate
**P1 parsing, directly and without any scoring labels.** Humans marked the skill
spans by hand, so `extract_skills()` can be measured against them: recall, and false
positives. This is the most objective test in this directory — the ground truth is a
span of text, not an opinion.

### What it CANNOT validate
Scoring, ranking or matching. A perfect parse still says nothing about whether the
weighted formula on top of it is sensible.

`parsing_check.py` reports recall twice, and the gap between the two is the finding:
- **raw recall** over every annotated skill, bounded above by vocabulary size, since
  `SKILL_VOCAB` holds only ~60 terms and anything outside it is unfindable;
- **in-vocabulary recall** over just the gold skills that exist in `SKILL_VOCAB`,
  which isolates matcher quality from vocabulary coverage.

Quoting raw recall alone would blame the regex for a vocabulary problem.

---

## 4. stress_intervals.py — 25 hand-written cases, no download

The only test here that probes **job matching**, because it is the only one where
resume and job description are both controlled. 25 cases with intervals written from
what a trustworthy ATS scorer *should* output, fixed before the scorer was run and
not adjusted afterwards.

Includes the three spec-mandated probes: an unrelated-industry resume must score
under 30, a near-perfect match must clear 70, and the job description pasted 20 times
must not exceed 50.

A FAIL is a finding about the scorer, not a broken case. The script prints the
category breakdown for every failure so each one traces to a component.

---

## Measured result — stress_intervals.py, 2026-07-27

SBERT active (`all-MiniLM-L6-v2`). **13/25 passed, 12 failed. All 12 failures are
ABOVE the interval — the scorer is uniformly too generous, never too harsh.**

Two of the three spec-mandated cases fail:

| Spec case | Requirement | Got | |
|---|---|---|---|
| 1 near-perfect match | > 70 | **89** | PASS |
| 3 unrelated industry (barista → backend) | < 30 | **55** | **FAIL** |
| 4 job description pasted 20× | ≤ 50 | **66** | **FAIL** |

Score range across all 25 cases: 24 .. 89.

### Root cause 1 — 45% of the weight is one signal counted three times

`parsing._count_entries` (`backend/app/services/parsing.py:123`) counts **date-range
regex hits across the entire document**, and `parse_resume` calls it separately for
work, education and projects. When any date range exists, all three sections return
the *same count*. The barista resume has three date ranges, so:

```
work=3  education=3  projects=3   ->   experience 96  education 100  projects 100
```

Experience + projects + education are 45% of the total weight and, in practice, are
a single measurement of "how many years appear in this document" — triple-counted,
and entirely blind to what the resume says. That is why a barista scores 96 on
Experience against a senior Python posting.

### Root cause 2 — only 20% of the score can respond to the job

Skills, experience, projects, education and formatting are all computed without ever
seeing the job description. Only `semantic` (20%) reads it. The maximum swing a job
description can produce is therefore **20 points**, and the count-based categories
saturate at 100 after three entries. Cases 12, 13 and 23 show the consequence:

| Case | semantic | total |
|---|---|---|
| 12 data scientist vs frontend posting | 1 | 77 |
| 13 frontend resume vs backend posting | 23 | 82 |
| 23 nurse vs backend posting | 1 | 52 |

The semantic component correctly identified all three as mismatches — it scored 1,
23 and 1 out of 100. It was outvoted. **"Under 30 for an unrelated industry" is
arithmetically unreachable** for any resume that parses at all: with semantic at 0,
the category floors (skills 25, experience 30, projects 25, education 40, formatting
50) still sum to 24, and a single date range lifts experience/education/projects to
near 100.

### Root cause 3 — an empty resume scores 36, not 0

`_semantic_score` returns the neutral **60** when the resume text is empty
(`scoring.py`, `if not job_description or not resume_text.strip()`). An empty upload
is not an unknown match, it is a non-match, but it is credited as average. Combined
with the floors, the empty resume scores 36 (case 5, FAIL) while the *name-only* and
*gibberish* resumes score 24 and PASS — text that parses to nothing scores lower than
no text at all.

### Root cause 4 — nothing penalises repetition

Case 4 (the posting pasted 20 times) gets skills=100 and semantic=64: it is a perfect
lexical self-match by construction, and no signal notices that the document is the
same 90 words repeated. Formatting only tests word count, and >1200 words costs 15
points off one 5%-weighted category.

### What this does NOT prove

The intervals are 25 cases I wrote. They are a specification of intended behaviour,
not a measured ground truth — a FAIL means the scorer disagrees with a stated
intention, not that a real recruiter would disagree. Cases 8–21 in particular encode
opinions about what a career changer or a contractor *should* score. The three
spec-mandated cases are the ones worth defending; the rest are directional.

Fixes belong in `app/services/`, which this directory does not touch.

---

## Honest summary of coverage

| Capability | Covered by | Strength |
|---|---|---|
| Parsing / skill extraction | Resume-Corpus NER | **Strong** — hand-marked ground truth |
| Quality ranking | CareerCorpus | **Moderate** — real expert labels, low ceiling, narrow range |
| Job matching | stress_intervals only | **Weak** — 25 cases I wrote myself; 12 currently FAIL |
| Distribution sanity | CareerCorpus + Kaggle | Moderate |

The weakest cell is the one the product sells. No public dataset in this list pairs
real resumes with real job descriptions and real hiring outcomes; that data arrives
only from consented live traffic. Until then, job-matching quality rests on 25
hand-written intervals, and should be described that way.
