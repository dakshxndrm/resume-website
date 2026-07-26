# eval/golden — the labeled dataset

One JSON object per line in `dataset.jsonl`:

```json
{
  "id": "a1",
  "human_score": 9,
  "job_description": "Backend Engineer. Build and scale REST APIs in Python ...",
  "resume_text": "PRIYA NAIR\nBackend Engineer\n\nEXPERIENCE\n...",
  "notes": "Clear hire. Every required skill present with evidence ..."
}
```

| Field | Meaning |
|---|---|
| `id` | Short unique handle. The current convention is JD-letter + rank (`a1`..`a5`). |
| `human_score` | **1–10 integer.** 10 = obvious hire for this specific job, 1 = no overlap at all. |
| `job_description` | The posting the resume is being judged against. Required — a score with no JD is not a judgement about fit. |
| `resume_text` | Plain text, `\n` for line breaks. What a parser would extract from the PDF. |
| `notes` | Why you gave that score. Free text. Not read by any code — it exists so a disagreement six months from now is resolvable. |

## What is in here now

15 hand-written synthetic examples: 3 job descriptions × 5 resumes each, spanning
clearly-strong to clearly-weak. They were written to span the range evenly, which
makes them **useful for catching gross failures and useless for measuring real
accuracy** — see the honesty section in `../README.md`.

The synthetic set is also *easier* than reality. Real resumes are messier, longer,
more ambiguous, and cluster in the middle of the scale rather than spreading
neatly across it.

## Adding real labeled examples

This is the part that actually matters. The synthetic set exists so the harness
runs today; real labels are what make its numbers mean something.

1. **Get the text.** Copy the extracted resume text (not the PDF) and the job
   description. Strip names, emails, phone numbers and links by hand — this file
   is committed to git.
2. **Score it 1–10 before looking at what the app says.** Anchoring on the app's
   score turns the benchmark into a mirror. Write your reasoning in `notes` first,
   then pick the number.
3. **Use the whole range.** The most common labeling failure is compressing
   everything into 5–8, which makes correlation look impressive for the wrong
   reason — a scorer can match a narrow band by outputting the mean.
4. **Append a line to `dataset.jsonl`.** Any unique `id` works; use something
   traceable like `real-2026-07-01-a`.
5. **Re-run `python eval/run_benchmark.py`.** Correlation will usually drop when
   real examples land. That is the benchmark getting more honest, not worse.

### Scoring rubric

Keep it consistent, or the correlation measures your mood rather than the scorer.

| Score | Meaning |
|---|---|
| 9–10 | Obvious hire. Every requirement evidenced, right seniority. |
| 7–8 | Strong. Would interview. Minor gaps or adjacent tooling. |
| 5–6 | Borderline. Real overlap but a substantive gap (seniority, a core skill, depth). |
| 3–4 | Weak. Wrong discipline or wrong level, though not absurd. |
| 1–2 | No meaningful overlap. |

### How many do you need

- **15 (now):** catches gross failures only. A correlation number from this is
  a smoke signal, not a measurement.
- **~50:** the confidence interval on Spearman is still roughly ±0.25. Enough to
  spot a genuinely broken change.
- **~200:** the point where a correlation is worth quoting, and where
  re-weighting the scoring formula against the data becomes defensible instead
  of guesswork.
- **Two labelers on an overlapping subset:** measure your own agreement first.
  If two humans only agree at ρ≈0.7, no scorer can beat 0.7 against your labels,
  and chasing that ceiling is chasing noise.
