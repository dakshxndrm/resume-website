# Resume Website — Project Plan (v3)

**Type:** Ambitious solo-built product — goal is real-world scale, "best-in-class" resume tool, usable by every user on the web
**Monetization:** Ad-supported, fully free to users (architected so a paid tier can be added later without a rewrite)
**Budget:** $0 now — build entirely on free tiers, reinvest once there's ad revenue
**Core differentiator:** A self-trained JEPA-style resume/job scorer, distilled from an LLM teacher, replacing the LLM as the core scorer over time

---

## 1. The LLM ↔ JEPA relationship (read this before building)

- **LLM (Gemini/Groq free tier, launch-day)**: generates the ATS-style feedback text and acts as the initial scorer. Fast to ship, but every call costs quota/money and you don't own it.
- **JEPA (trained by you, in the background)**: a self-supervised embedding model. It does **not** write text — it scores resume↔job fit. Trained in two stages:
  1. **Self-supervised pretraining** on public resume datasets (Kaggle, GitHub, research-paper corpora) using the JEPA masked-embedding-prediction objective — no labels needed.
  2. **Distillation from the LLM**: once the site is live, every LLM-scored resume (with user consent) becomes a training example — JEPA learns to reproduce the LLM's score. This is standard **knowledge distillation** (teacher = LLM, student = JEPA).
- **Swap-in, not a rewrite**: once JEPA's scores match the LLM's on a held-out validation set, route free-tier scoring through JEPA (near-zero marginal cost) and reserve the LLM for suggestion-text generation only, or a lightweight distilled/template generator once that's viable too.
- **Never build your own foundation LLM from scratch** — not feasible solo/bootstrapped. If a text generator is eventually needed in-house, distill a small open-weight model, don't pretrain one.

---

## 2. System architecture

```
Resume Upload → PyMuPDF/pdfplumber + OCR fallback → spaCy NER → Skill Extraction
                                                          │
                                                   Normalization
                                          (Python→python3→Py, ReactJS→React)
                                                          │
Job Description ──────────────────► same parsing pipeline │
                                                          │
                                          RAG: retrieve canonical skills
                                          for the job title from O*NET/ESCO
                                          (open, structured, free datasets)
                                                          │
                              ┌───────────────────────────┼───────────────────────┐
                              │                            │                       │
                        BM25 keyword score        Sentence-BERT / JEPA        Structured features
                        (free, local, always on)   semantic similarity        (experience, education,
                                                    (JEPA replaces SBERT       certs, projects, format)
                                                    once distilled & validated)
                              │                            │                       │
                              └────────────── Weighted Scoring Engine ─────────────┘
                                   Skills 30% · Experience 25% · Semantic 20%
                                   Projects 10% · Education 10% · Formatting 5%
                                                          │
                                              Score (0–100) + gap list
                                                          │
                              LLM (launch) → readable suggestions, logged as
                              JEPA training data (consented) for future distillation
                                                          │
                                             Resume Builder / Editor
                                          (same scoring engine, live rescoring)
```

**Tech stack (all free-tier at launch)**

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js + TypeScript + Tailwind | Free hosting on Vercel |
| Backend | FastAPI (Python) | Same language as ML code |
| DB | Postgres via Supabase or Neon (free tier) | Managed, free, easy to scale later |
| Vector store | pgvector on the same free Postgres | No separate service needed early |
| LLM (launch) | Gemini API free tier (1,500 req/day, no card) primary; Groq free tier as fallback/secondary | Generous free limits, route between them so one provider's cap doesn't take the site down |
| Baseline semantic | sentence-transformers (local, free) | Always-on fallback and benchmark for JEPA |
| ML training | PyTorch, trained on Kaggle/Colab free GPU | No infra cost for JEPA training |
| Resume data model | JSON Resume schema | Open, portable |
| Open knowledge base | O*NET / ESCO (free, structured) | Grounds RAG in real labor-market data |
| PDF export | WeasyPrint / react-pdf | Free |
| Hosting (backend) | Railway/Render free tier → paid once revenue exists | Cheap start, easy migration |
| Ads | Google AdSense (or resume-niche ad network once traffic justifies it) | Standard, low integration effort |

---

## 3. Phased roadmap

### Phase 0 — Data & legal foundation (1–2 weeks)
- JSON Resume as canonical data model.
- Ingest O*NET/ESCO into a normalized skills table.
- Collect a small public resume/job-description dataset to bootstrap JEPA pretraining.
- **Privacy policy + explicit consent checkbox** for storing/using resume data — required before any real users touch the product.

### Phase 1 — MVP: launch fast on proven components (3–4 weeks)
- Resume parsing pipeline (PyMuPDF/pdfplumber + OCR, spaCy NER, normalization).
- BM25 + Sentence-BERT scoring, weighted scoring formula.
- LLM-generated suggestions (Gemini free tier, Groq fallback), with usage rate-limited per user/day to stay inside free quotas.
- Resume builder wizard + structured editor (JSON Resume in/out).
- Ship this publicly — first real users, first ad impressions, first data for distillation.

### Phase 2 — RAG grounding (2 weeks)
- Embed O*NET/ESCO into pgvector.
- Retrieve job-role-specific skills, diff against resume → gap list feeding both the score and the LLM's suggestion prompt (grounds the LLM instead of letting it guess).

### Phase 3 — JEPA pretraining (3–4 weeks, background track)
- Self-supervised training on public resume corpora, Kaggle/Colab free GPU.
- Not user-facing yet — pure research/engineering track that doesn't block Phase 1/2 shipping.

### Phase 4 — Distillation: JEPA learns from the LLM (2–4 weeks, ongoing)
- Every consented user resume + LLM score/suggestion becomes a training pair.
- Fine-tune JEPA so its similarity scores approximate the LLM's judgments.
- Continuously validate against Sentence-BERT baseline and the LLM teacher — only promote JEPA to production once it matches quality.

### Phase 5 — Swap-in (ongoing)
- A/B test JEPA-based scoring vs LLM-based on a slice of traffic.
- Once validated, JEPA becomes the default free-tier scorer (near-zero marginal cost); LLM usage shrinks to suggestion-text generation, later possibly a small distilled generator.

### Phase 6 — Scale hardening (once traffic grows)
- Move off free-tier hosting/DB as ad revenue allows.
- Add caching for repeated resume/job-description pairs to cut LLM calls further.
- Consider a paid tier if ad revenue doesn't cover LLM/infra costs at scale (architecture already supports this without a rewrite).

### Phase 7 — GNN matching layer (future/optional)
- Represent O*NET/ESCO as a knowledge graph; train a GNN for bidirectional resume↔job matching.
- Only after core product + monetization are validated — genuine research depth, not a launch blocker.

---

## 4. Immediate next steps

1. Repo structure: `frontend/`, `backend/`, `ml/`, `data/`.
2. Set up Supabase/Neon Postgres + pgvector, Vercel + Railway/Render free hosting.
3. Get Gemini + Groq free-tier API keys, build a thin LLM router with fallback.
4. Build Phase 1 parsing + BM25/SBERT scoring pipeline — get to a working, shippable MVP before touching JEPA.
5. Draft privacy policy + consent flow before any real user data is collected.
6. Start Phase 3 (JEPA pretraining) as a parallel, non-blocking track once Phase 1 is stable.

## 5. Risks to watch

- **Free-tier ceilings**: Gemini's 1,500 req/day and Groq's daily caps are shared across *all* users — a viral spike can exhaust them fast. The BM25/SBERT-first, LLM-for-suggestions-only design exists specifically to stretch this.
- **Ad economics**: resume tools are low-frequency/high-intent — ad revenue per user is typically low. Watch actual numbers once live; the architecture supports adding a paid tier if ad revenue doesn't cover costs.
- **JEPA data volume**: distillation quality depends on enough consented real usage data — this will take real user traffic (from Phase 1 launch) to accumulate, not just public datasets.
- **Privacy/compliance**: storing resumes (PII) at "every user on the web" scale means GDPR/CCPA exposure eventually — consent flow and a deletion mechanism aren't optional once you're not just testing with friends.
