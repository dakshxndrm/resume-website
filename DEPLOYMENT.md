# Deployment checklist — Render or Railway

Manual steps. Nothing here deploys anything for you.

## 0. Before you start

- Push the current branch — both hosts deploy from a connected GitHub repo.
- Pin the Python version so the host doesn't pick something torch 2.4.1 doesn't
  support (it does not support 3.13+). Add `backend/runtime.txt`:
  ```
  python-3.12.7
  ```
  (Railway/nixpacks reads this too; Render reads `PYTHON_VERSION` as an env var
  instead — set it in step 2 as well, belt and braces.)

## 1. Database — Neon Postgres

Already on Neon (`DATABASE_URL` in `backend/.env`). Nothing to migrate — same
connection string works from Render/Railway, since Neon requires TLS from any
client and `app/core/db.py` already forces `sslmode=require`. Just copy the value
into the host's env vars in step 2.

## 2. Backend service (Render: "Web Service" / Railway: new service from repo, root `backend/`)

**Build command** (CPU-only torch first, or the default pip resolve pulls the
~2.5GB CUDA build and blows the build-time/image-size budget on a free tier):
```
pip install torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt
```

**Start command:**
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Environment variables to set** (from `backend/.env` — none of these should be
committed; `backend/.env` itself already isn't):

| Var | Value | Notes |
|---|---|---|
| `DATABASE_URL` | your Neon connection string | same as local |
| `FRONTEND_ORIGIN` | `https://<your-frontend-domain>` | see step 4 — must be the exact prod frontend URL, no trailing slash |
| `FIREBASE_CREDENTIALS_B64` | base64 of `firebase-service-account.json` | see step 3 — replaces `FIREBASE_CREDENTIALS` (file path) in prod |
| `GROQ_API_KEY` | your Groq key | |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` (or current) | |
| `GEMINI_API_KEY` | your Gemini key, if set | read into settings, not wired to code yet — safe to leave blank |
| `LLM_DAILY_LIMIT_USER` | `30` | optional, has a default |
| `LLM_DAILY_LIMIT_ANON` | `5` | optional, has a default |
| `SUGGESTION_CACHE_TTL_HOURS` | `720` | optional, has a default |
| `PYTHON_VERSION` | `3.12.7` | Render-specific; see step 0 |

Do **not** set `FIREBASE_CREDENTIALS` in prod — leave it unset so the code falls
back to `FIREBASE_CREDENTIALS_B64` (see step 3; `_init_firebase()` in
`app/core/auth.py` checks the base64 var first).

## 3. Firebase service account → base64 env var

`firebase-service-account.json` is a file on disk locally; Render/Railway don't
give you a real filesystem to drop secret files into, so it goes in as a base64
string instead. `app/core/auth.py` already decodes it straight into a dict at
startup — no temp file involved.

Encode it:
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("backend\firebase-service-account.json"))
```
```bash
base64 -w0 backend/firebase-service-account.json
```
Paste the output as `FIREBASE_CREDENTIALS_B64` in step 2's env vars. Never commit
the raw JSON or the base64 string — treat the base64 string with the same care as
the file itself, it's the same secret.

## 4. Firebase Console — authorized domains

Console-only, no code: **Authentication → Settings → Authorized domains** → add
your production frontend domain (e.g. `yourapp.onrender.com` or your custom
domain). Without this, Firebase Auth rejects sign-in from the deployed frontend
even with correct env vars — a common "works locally, breaks in prod" trap.

## 5. Frontend service (Render: "Web Service", root `frontend/`, or Railway equivalent)

**Build command:** `npm install && npm run build`
**Start command:** `npm run start`

**Environment variables** (all `NEXT_PUBLIC_*` vars are baked into the JS bundle
at *build* time, not read at runtime — set them before the build step runs, and
re-deploy/re-build if you ever change one):

| Var | Value |
|---|---|
| `NEXT_PUBLIC_FIREBASE_API_KEY` | from Firebase console |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | from Firebase console |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | from Firebase console |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | from Firebase console |
| `NEXT_PUBLIC_BACKEND_URL` | the backend service's public URL from step 2, e.g. `https://resumeai-backend.onrender.com` (no trailing slash) |

`frontend/src/lib/api.ts` fetches this URL directly from the browser (not through
the `next.config.js` rewrite — that rewrite exists but nothing in `lib/api.ts`
uses it), so the backend's CORS `FRONTEND_ORIGIN` (step 2) and this URL must point
at each other correctly or every request 400s on CORS before it reaches your code.

## 6. SBERT cold-start risk on free tiers

`warm_semantic_model()` blocks startup until the `all-MiniLM-L6-v2` model is
loaded — by design, so the process never reports ready without working semantic
scoring (see `app/main.py`'s lifespan comment). Locally this costs ~10-14s on a
warm model cache; the *first ever* boot on a machine also downloads ~90MB of
weights on top of that.

Free tiers on both Render and Railway spin the service down after a period of no
traffic, so every wake-up re-pays this cost — and if the model cache doesn't
persist across spin-downs, it re-pays the 90MB download too, not just the load
time. Pick one:

- **Paid "always-on" tier** — no spin-down, cold start happens once at deploy,
  never again. Simplest fix if the cost is acceptable.
- **Keep-alive ping** — an external cron (e.g. a GitHub Actions scheduled
  workflow, or a free uptime-monitor like UptimeRobot) hitting `/llm/health` or
  another cheap endpoint every ~10 minutes, before the platform's idle timeout.
  Keeps the free tier from spinning down at all, at the cost of running your free
  quota's hours continuously.
- **Persistent volume for the model cache** (Railway volumes; Render persistent
  disks on paid plans only — not available on Render's free tier) mounted at
  `~/.cache/huggingface` (sentence-transformers' default cache dir) — doesn't
  avoid the ~10-14s load time on a cold process, but does avoid the ~90MB
  re-download on every spin-down/spin-up cycle if the disk persists.

None of these need a code change — `SBERT_DISABLED=1` already exists as an escape
hatch (falls back to BM25 + keyword coverage, see `scoring.py`) if the model
ever becomes a genuine availability problem rather than just slow.

## 7. Post-deploy smoke test

- `GET <backend-url>/llm/health` → `{"llm": "ok", ...}` or `{"llm": "disabled"}`
  if `GROQ_API_KEY` isn't set — either is fine, an error isn't.
- Sign in on the deployed frontend, confirm Firebase Auth succeeds (this is what
  step 4 protects against failing).
- Upload a resume, confirm `/score/upload` returns a report — exercises DB
  connectivity, SBERT, and the full request path end to end.
