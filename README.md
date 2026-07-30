# AI Resume Scoring App

A full-stack web app that scores resumes against job descriptions using BM25 + keyword coverage + SBERT semantic similarity, with AI-generated improvement suggestions (Groq LLM, rule-based fallback).

## Tech Stack

- **Frontend:** Next.js
- **Backend:** FastAPI
- **Database:** Neon Postgres (SSL enforced)
- **Auth:** Firebase (Google sign-in)
- **AI suggestions:** Groq (`llama-3.3-70b-versatile`) with rule-based fallback
- **Semantic scoring:** sentence-transformers (`all-MiniLM-L6-v2` / SBERT)
- **Resume parsing:** PyMuPDF / python-docx / pdfplumber
- **Scoring:** BM25 + keyword coverage + SBERT cosine similarity
- **PDF export:** reportlab

## Project Structure

```
resume website/
├── backend/
│   ├── app/
│   │   ├── api/routes.py          # all endpoints
│   │   ├── services/
│   │   │   ├── parsing.py         # resume parsing, section splitting
│   │   │   ├── scoring.py         # BM25 + keywords + SBERT scoring
│   │   │   ├── llm_router.py      # Groq calls + fail-safe fallback
│   │   │   └── llm_cache.py       # suggestion caching + rate limits
│   │   ├── models/models.py       # SQLAlchemy models
│   │   └── core/                  # config, db, auth
│   ├── scripts/
│   │   ├── ingest_onet.py         # O*NET skills ingestion (see Pending)
│   │   └── data/                  # O*NET CSVs (gitignored)
│   ├── tests/                     # 115+ tests, pytest
│   └── eval/                      # OLDER benchmark dir — see Pending #1
├── eval/external/                 # CURRENT benchmark harness
│   ├── stress_intervals.py        # 25 hand-written scoring test cases
│   ├── careercorpus.py            # inter-annotator-agreement validation
│   └── parsing_check.py           # skill-extraction recall check
├── frontend/
│   └── src/
│       ├── features/
│       │   ├── upload/            # resume + JD upload
│       │   ├── editor/            # live-scoring resume editor
│       │   ├── builder/           # guided resume builder
│       │   └── account/           # privacy controls
│       └── lib/                   # api client, firebase config
├── ml/                            # PARKED — see Pending #4
└── docs/                          # PROJECT_PLAN.md, WEBSITE_BLUEPRINT.md
```

## Completed

- **P1** — Real resume parsing, BM25 + keyword-coverage scoring, JD matching, missing-skills detection
- **P2** — Neon Postgres persistence
- **P3** — Groq LLM suggestions with rule-based fail-safe
- **P4** — Full resume editor (repeatable sections, live re-scoring, PDF export, report→editor carryover)
- **P5** — 82+ test suite (SQLite in-memory overrides)
- **Phase 0** — Consent + privacy (`PATCH /users/consent`, `DELETE /users/me`, privacy page)
- **SBERT integration** — real cosine similarity scoring, model warmed at boot via FastAPI lifespan (not on first request)
- **LLM cost controls** — suggestion caching (sha256 of normalized resume+JD), per-user (30/day) and anon-IP (5/day) rate limits, graceful fallback to rule-based suggestions on cache miss/limit/429
- **Benchmark harness** (`eval/external/`) — 25-case stress test, CareerCorpus IAA validation, skill-extraction recall check
- **Scorer bug fixes** — found via the benchmark harness:
  - Section-scoped entry counting (was triple-counting date ranges across the whole document)
  - Skills score now checks against the job description (was pure resume skill count)
  - Empty resumes now score 0 instead of a neutral 60
  - Repetition/keyword-stuffing penalty added
- **O*NET data ingestion** — `ingest_onet.py` parses O*NET's Essential Skills + Software Skills CSVs into an `onet_skills` table, idempotent upsert, verified against real data (8,940 + 31,821 rows)

## Pending — To Implement Later

### 1. Fix `backend/eval/` (broken, separate from `eval/external/`)
- `backend/eval/run_benchmark.py` and `test_properties.py` still import the old `_count_entries` function signature, which was renamed to `_count_section_entries` during the scorer fix. This directory currently fails on import.
- `backend/pytest.ini`'s `testpaths = tests` means this failure is silently skipped by the normal test run — nobody notices unless you run `pytest backend/eval` directly.
- **Decision needed:** either update it to the new API, or deprecate it in favor of `eval/external/` (which duplicates its purpose) and note that clearly in a README.

### 2. Stale test assertions in `test_scoring.py`
- `test_no_job_description_is_neutral` and `test_no_job_description_stays_neutral_regardless_of_sbert` still assert the *old* behavior (empty resume + no JD = 60). The scorer fix correctly changed empty text to score 0. These two tests need updating, plus a new test confirming a real non-empty resume with no JD still returns the neutral 60.

### 3. Scorer calibration — stress test at 19/25
- Current `eval/external/stress_intervals.py` pass rate: 19/25. 2 of 3 spec-mandated cases pass.
- **Case 3 (unrelated industry)** scores 31, needs <30 — a barista resume against a senior Python job still scores too high on experience (74) and education (70). The base floor in those formulas needs lowering.
- Other near-misses to revisit: case 11 (data-scientist-on-target), case 14 (paraphrased-skills), case 15 (skills-only), case 19 (overlong-resume), case 21 (PhD-no-industry).

### 4. RAG / O*NET skill suggestions (Prompt 2) — not built yet
Only the data ingestion (`ingest_onet.py`) exists. Still to do:
- Enable **pgvector** extension on the Neon Postgres DB (`CREATE EXTENSION IF NOT EXISTS vector;`), add an embeddings column to the `onet_skills` table
- `app/services/skills_rag.py` — `get_canonical_skills(job_title_or_description)` using vector similarity, with a keyword fallback if pgvector/table is unavailable
- Reuse the **already-loaded SBERT model** from `scoring.py` for embeddings — do not load a second model instance
- Rewire `/skills/suggest` (currently a hardcoded stub) to call `skills_rag` — keep the response shape `{"skills": [...]}` unchanged so the frontend needs no changes
- Inject retrieved skills into **both** the Groq prompt and the rule-based fallback suggestions (the fallback injection is what actually reduces reliance on the LLM)
- Cap injected skills at ~15 (token budget)
- Fail-safe: retrieval failure or LLM failure must still return valid suggestions

### 5. Deployment (target: Render or Railway)
Nothing is live yet — only localhost. Known risks/tasks:
- **SBERT cold-start** (~13.7s boot, ~90MB model download) is risky on free-tier hosts that spin down idle services — needs a mitigation (paid tier, keep-alive ping, or persistent volume for model cache)
- Move all secrets (`.env`, `firebase-service-account.json`) to host environment variables — the Firebase service account JSON likely needs base64 encoding for env-var storage
- Update `FRONTEND_ORIGIN` (CORS), Firebase authorized domains, and `NEXT_PUBLIC_BACKEND_URL` to production values (currently localhost)
- Neon Postgres needs no changes — already cloud-hosted

### 6. Templates (post-deployment)
- "Use This Template" buttons in the resume builder are currently static/non-functional

### 7. JEPA / ML track — explicitly parked
- Lives in `ml/` (isolated — safe to work on without touching backend/frontend)
- Conclusion from prior investigation: this track can **only** ever replace the SBERT semantic scoring component (20% of total score) — it cannot replace the Groq LLM (Groq only rewrites suggestion *text*; score is 100% computed locally before Groq is ever called)
- **Data blocker:** only ~16k real resume-text documents obtainable from public sources combined, against a 50k–100k floor needed for pretraining
- **Licence concern:** 88% of the obtainable corpus (Resume-Classification-Dataset) was scraped from LiveCareer/Google/Bing with no stated licence — real people's resumes, used in a commercial product. Do not ship any model trained on it.
- **Real path forward:** needs 5k–10k consented `(resume, job, LLM-score)` triples collected from live traffic post-launch (this is why the Phase 0 consent system was built first)

## Development Notes

- **Git workflow:** local is always source of truth. Never `git pull` or merge from remote — use `git fetch` + backup branch + `git push --force-with-lease`. (A prior `git pull --allow-unrelated-histories` mid-session reverted 6 completed files — this rule exists because of that incident.)
- **Parallel work:** `ml/` and `eval/external/` are isolated and safe to work on in parallel with backend work. Anything touching `backend/app` or `frontend/src` should be done one prompt at a time, verified, and committed before starting the next — never two overlapping backend changes in the same session.
- **Testing:** `cd backend && python -m pytest -q` (currently 113 passed, 2 known-stale failures — see Pending #2). `cd frontend && npx tsc --noEmit` for type checking.
- **Benchmarking:** `python eval/external/stress_intervals.py` — the harness that originally caught the scorer bugs. Run after any change to `scoring.py` or `parsing.py`.
