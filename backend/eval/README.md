# eval/ — measuring the scorer instead of trusting it

Two things live here, and they answer different questions.

```bash
cd backend
python eval/run_benchmark.py              # does the score agree with human judgement?
python -m pytest eval/test_properties.py -v   # does the scorer behave sanely at all?
```

Neither touches `app/`. Nothing in this folder may be used to justify tuning
`scoring.py` until the golden set contains real labeled data — see the honesty
section at the bottom.

---

## Where the weights came from

`app/services/scoring.py` weights each component:

```
skills 30% · experience 25% · semantic 20% · projects 10% · education 10% · formatting 5%
```

**These numbers were not fitted to anything.** They are expert-judgment priors:
someone's reasonable belief about what matters in a resume, written down in
`docs/PROJECT_PLAN.md` before any data existed. The same goes for the sub-score
formulas — `min(100, 25 + len(skills) * 8)` is a shape someone picked because it
looked sensible, not a curve fitted to outcomes.

That is a legitimate way to start. It is not a legitimate thing to leave
unexamined, and it is definitely not something to describe to users as accuracy.
This folder exists to make the gap measurable.

Fitting the weights properly needs a few hundred real labeled examples and a
train/test split. Until then, changing a weight because it improves the number
in `run_benchmark.py` is overfitting to 15 examples that were written by the same
person who set the weights.

---

## 1. `run_benchmark.py` — agreement with human judgement

Scores every example in `golden/dataset.jsonl` with the live scorer and compares
against the human 1–10 labels.

| Metric | What it means |
|---|---|
| **Spearman** | Does the scorer put the resumes in the same *order* a human would? Immune to the scorer being systematically high or low. This is the number that matters most. |
| **Pearson** | Same, but assumes the relationship is a straight line. Diverging from Spearman means the scorer's response is curved. |
| **MAE** | Average distance in points after mapping human 1–10 onto 0–100 linearly. Answers "how far off is the number a user actually sees". |
| **Mean signed error** | The same error with its sign kept, so systematic optimism or pessimism shows up instead of averaging out. |
| **Distribution histogram** | Where the scores land. |
| **Tightest 15-point band** | Flags if over 60% of scores are crammed into a 15-point window. A scorer that outputs 60–75 for everything can score well on correlation while being useless to a user. |

**Thresholds** (in the source, stated in the verdict line): Spearman ≥ 0.60,
MAE ≤ 20 points, tightest band < 60%. These are "obviously broken vs not
obviously broken" lines, not quality targets — human labelers typically agree
with each other only at ρ ≈ 0.7–0.8, which is the real ceiling.

Exit code 0 on PASS, 1 on FAIL, so CI can consume it.

### What it does NOT prove

- **Not accuracy.** 15 synthetic examples written by one person, who also wrote
  the labels. The scorer is being graded against its author's intuitions, on
  resumes composed to be unambiguous.
- **Not generalisation.** Real resumes are longer, messier, more ambiguous, and
  cluster in the middle of the scale instead of spreading evenly across it.
- **Not that a user's score is right.** It says the *ordering* is defensible on
  easy cases.
- **Nothing about outcomes.** No one has checked whether a high score correlates
  with actually getting an interview. That is the question that matters, and this
  harness cannot answer it.

---

## 2. `test_properties.py` — sanity, whatever the weights are

Properties that must hold for any sane scorer, so they stay valid when the
weights change.

| Property | What it proves |
|---|---|
| **Determinism** | Same input, same output, every run. A score a user cannot reproduce is untrustworthy, and it makes every other measurement here noise. |
| **Monotonicity** | Adding a JD-required skill raises the score; deleting all work experience lowers it. The score responds to the things it claims to measure, in the right direction. |
| **Discrimination** | A matched resume beats an unrelated one by more than 25 points on the same JD, and a resume scores higher against its own field's JD than another's. |
| **Bounds** | 8 adversarial inputs (empty, whitespace, 20k repeated words, punctuation, unicode, 5k newlines) × 4 job descriptions never produce a total or category outside 0–100. |
| **Gaming resistance** | Pasting the job ad 20 times must not score near the top. |

These are all necessary and none are sufficient. A scorer that returns
`hash(text) % 100` would fail them; a scorer that returns a well-behaved,
confident, *wrong* number can pass every one.

This suite is deliberately outside `pytest.ini`'s `testpaths`, so `pytest` from
`backend/` does not collect it. That is on purpose: **this suite is allowed to
fail.** The app test suite verifies contracts and must stay green; this one
measures honest behaviour. Merging them would create pressure to weaken a
measurement to keep CI green.

---

## Current findings (2026-07-27)

Run both yourself; this is what they said at the time of writing.

**Benchmark: PASS.** Spearman +0.969, Pearson +0.966, MAE 14.8 pts, scores span
36–86, tightest 15-point band holds 33%.

Read that 0.969 with suspicion, not pride. It is high because the golden set is
synthetic, evenly spread, and written by the same person who set the weights.
The interesting number is the **+11.5 point bias**: the scorer runs high, and it
does so worst at the bottom — the barista resume was labeled 1/10 and scored 36.
The floor is not zero. A weak resume is told it is a third of the way to good.

**Properties: 42 pass, 1 fails.**

The failure is real and is left failing:

```
test_semantic_component_prefers_a_real_resume_over_the_pasted_ad
  semantic rates the pasted job ad (64) above a real resume (50)
```

The semantic component is text similarity, so the text most similar to a job
description is that job description. A genuine resume describing the same work in
its own words looks *less* similar than a copy of the ad. Full breakdown:

| | total | skills | experience | semantic | projects | education | formatting |
|---|---:|---:|---:|---:|---:|---:|---:|
| Genuine matched resume | 86 | 97 | 96 | **50** | 100 | 100 | 60 |
| Job ad pasted 20× | 67 | 100 | 52 | **64** | 25 | 40 | 85 |
| Unrelated (barista) | 36 | 25 | 52 | 0 | 50 | 70 | 60 |

Keyword stuffing does lose overall (67 vs 86) — but only because the structural
components outvote the semantic one. That is luck, not design, and the margin to
the 70-point "near the top" bar is 3 points.

Two more things the table shows that no test asserts yet: the barista resume gets
70 for education and 50 for projects, because those sub-scores mostly count
whether headings exist; and the genuine resume is penalised to 60 on formatting
for being under 150 words, which is an artefact of these being short synthetic
samples rather than a real signal.

---

## Honest summary

- The weights are **expert-judgment priors, not fitted parameters**. Nobody has
  demonstrated that 30/25/20/10/10/5 beats 25/25/25/10/10/5, or a flat average.
- The golden set is **synthetic and self-authored**. Its correlation number is a
  smoke test, not evidence.
- The scorer is **directionally sensible and systematically generous**, with a
  floor around 36 rather than 0.
- The **semantic component is gameable** and currently rates a pasted job ad
  above a real resume.

The single highest-value next step is not tuning anything. It is putting 50 real
labeled examples in `golden/dataset.jsonl` — see `golden/README.md`.
