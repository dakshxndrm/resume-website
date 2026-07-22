# ResumeAI — free ATS resume scoring, building & improvement

Monorepo. See `docs/PROJECT_PLAN.md` (architecture & ML roadmap) and `docs/WEBSITE_BLUEPRINT.md` (design system & UX rules).

```
frontend/   Next.js 14 + TypeScript + Tailwind + Framer Motion + Firebase (Google login)
backend/    FastAPI + SQLAlchemy + PostgreSQL + firebase-admin (token verify)
ml/         JEPA pretraining / distillation / eval (Phase 3+, empty for now)
data/       O*NET / ESCO ingestion (Phase 0/2, empty for now)
docs/       plans & blueprints
```

## Run the frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # fill Firebase keys (see below)
npm run dev                        # http://localhost:3000
```

Works **without** any configuration: pages render, upload/builder flows fall back to a demo report until the backend + Firebase are configured.

## Run the backend

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate    # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # fill DATABASE_URL (Supabase/Neon free tier works)
uvicorn app.main:app --reload      # http://localhost:8000  (interactive docs at /docs)
```

Tables auto-create on startup in dev. Use Alembic for real migrations later.

## Firebase (Google login) setup

1. [console.firebase.google.com](https://console.firebase.google.com) → create project → Authentication → enable **Google** provider.
2. Project settings → *Your apps* → add **Web app** → copy the config values into `frontend/.env.local` (`NEXT_PUBLIC_FIREBASE_*`).
3. Project settings → *Service accounts* → **Generate new private key** → save as `backend/firebase-service-account.json`.

Flow: Google popup (frontend) → Firebase ID token attached to every API call → backend verifies with firebase-admin → user row created in Postgres (`/auth/sync`). Firebase = identity only; **all data lives in Postgres**.

## Where the backend gets real (stubs → Phase work)

| Stub | File | Replaced in |
|---|---|---|
| Scoring heuristic | `backend/app/services/scoring.py` | Phase 1: parsing + BM25 + Sentence-BERT, weighted formula |
| File parsing | `POST /score/upload` in `routes.py` | Phase 1: PyMuPDF/pdfplumber + spaCy NER |
| Skill suggestions | `GET /skills/suggest` | Phase 2: RAG over O*NET/ESCO (pgvector) |
| LLM suggestions | `backend/app/services/llm_router.py` | Phase 1: Gemini free tier + Groq fallback |
| Semantic scorer | inside scoring | Phase 5: JEPA (distilled from LLM, `ml/`) |

`training_examples` table already exists — consented (resume, LLM output) pairs accumulate there for JEPA distillation (Phase 4).

## Tests

```bash
cd backend && pip install pytest && pytest        # scoring engine tests
```

## Note

`npm install` could not be run in the sandbox this project was scaffolded in (registry access blocked), so run it locally the first time — if TypeScript reports any small issue, it will point to the exact file/line.
