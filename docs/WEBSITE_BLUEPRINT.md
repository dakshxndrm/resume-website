# Website Blueprint — ResumeAI (working name)

> This document is the single source of truth for building the frontend. Follow it exactly. Every design decision below is derived from the 20 UX principles (visual hierarchy, white space, one primary action, Hick's law, F-pattern, consistency, recognition over memory, speed, mobile-first, typography, color, contrast, progressive disclosure, feedback, familiar patterns, accessibility, cognitive load, micro-animations, trust, user goals).

---

## 1. Product pages & the ONE primary action per page

| Page | Route | Primary action (only one CTA) | 10-second answer |
|---|---|---|---|
| Landing | `/` | **Check My Resume Score →** | "Free ATS score in 30 seconds" |
| Score Report | `/report/[id]` | **Fix My Resume →** | "Here's your score + what's wrong" |
| Builder | `/builder` | **Continue** (wizard step) | "Build a role-targeted resume" |
| Editor | `/editor/[id]` | **Save** (auto-save; button = Export PDF) | "Edit + live re-score" |
| Templates | `/templates` | **Use This Template** | "Pick a look, content carries over" |
| About/Trust | `/about` | **Try It Free** | "Who built this, why trust it" |

Nav: max 4 items (Hick's law) — `Score Check · Builder · Templates · About` + logo home link + profile avatar. Nothing else.

---

## 2. Design system

### 2.1 Color (6 tokens only — never add more)

```css
--color-primary:   #4F46E5;  /* indigo — CTAs, links, active states */
--color-secondary: #0F172A;  /* near-black slate — headings, nav */
--color-accent:    #10B981;  /* emerald — score gains, success moments */
--color-neutral:   #64748B;  /* slate gray — body text, borders (lighter tints via opacity) */
--color-success:   #10B981;
--color-error:     #EF4444;
/* Backgrounds: white + #F8FAFC section alternation. That's it. */
```

Score gauge is the ONE place allowed a gradient: red (#EF4444) → amber (#F59E0B) → emerald (#10B981), mapped 0–100.

### 2.2 Typography

- Font: **Inter** (variable, self-hosted via `next/font` — zero layout shift, no external request).
- Body: 16px mobile / 18px desktop, line-height 1.6, max-width **68ch**.
- Scale (1.25 ratio): 13 / 16 / 20 / 25 / 31 / 39 / 49px. Landing hero may use 61px desktop.
- Headings: weight 700, tracking -0.02em. Body: weight 400. Bold keywords inside paragraphs for F-pattern scanning.

### 2.3 Spacing & layout

- 4px base unit. Allowed steps: 4, 8, 12, 16, 24, 32, 48, 64, 96, 128.
- Section vertical padding: 96px desktop / 64px mobile. Generous — white space is the premium signal.
- Container: max-width 1200px, 24px side padding mobile.
- Grid: 12-col desktop, 4-col mobile.

### 2.4 Components (consistency contract)

Every instance identical — same radius, same shadow, same animation:

- **Radius**: 12px cards, 8px buttons/inputs, 999px pills/badges.
- **Buttons**: primary = filled indigo, white text, 8px radius, `hover: translateY(-1px) + shadow-md`, `active: translateY(0)`, 150ms ease-out. Secondary = ghost with 1px border. Destructive = error red, always with confirm.
- **Inputs**: 1px neutral border, focus = 2px primary ring (`focus-visible`), label always visible (no placeholder-as-label), inline error text below in error red.
- **Cards**: white, 1px border `neutral/15%`, shadow-sm, hover shadow-md 200ms.
- **Feedback states — every async action MUST show one of**: skeleton (loading lists), spinner-in-button + disabled (submitting), toast top-right (✓ Saved / ✗ error with reason), inline error (validation). Never a silent action.

### 2.5 Motion spec (delight without distraction)

Library: **Framer Motion**. Rules:

- Durations: micro 150ms · standard 250ms · page/section 400ms. Easing: `cubic-bezier(0.22, 1, 0.36, 1)`.
- **Score gauge**: animated count-up 0 → score over 1.2s with spring — this is the product's signature moment, make it feel earned.
- Section entrances on landing: fade + 24px rise, `whileInView`, once only, 60ms stagger between children.
- Suggestion cards: stagger in 60ms apart. Applying a suggestion: card collapses, score ticks up with a brief emerald pulse (recognition of progress).
- Page transitions: 200ms crossfade max. No slide-in pages.
- Hard rules: nothing animates longer than 1.2s; no looping/idle animations; `prefers-reduced-motion` disables all non-essential motion (accessibility, non-negotiable); animate only `transform` and `opacity` (GPU-composited, keeps 60fps).

---

## 3. Page blueprints (F-pattern, hierarchy, progressive disclosure)

### 3.1 Landing `/`

```
[Nav: logo · 4 links · avatar]                          ← thin, sticky, blur bg
[HERO — 70vh, huge white space]
   H1 49–61px: "Is your resume beating the ATS?"
   Sub 20px neutral: "Free score in 30 seconds. No sign-up to try."
   [ Check My Resume Score → ]   ← the only filled button above the fold
   (drag-and-drop upload zone doubles as the CTA — drop PDF anywhere in hero)
[SOCIAL PROOF strip]  "12,480 resumes scored" · ★ ratings · privacy badge   ← trust signals
[HOW IT WORKS — 3 cards, icons, ≤12 words each]        ← scanning, not reading
[LIVE DEMO section — animated fake score report]        ← show, don't tell
[FEATURES — 4 cards max]                                ← Hick's law
[FAQ accordion]                                          ← progressive disclosure
[FOOTER — minimal: privacy, contact, GitHub]
```

### 3.2 Score Report `/report/[id]`

```
[Score gauge — huge, center, animated count-up]          ← look here first (2-sec rule)
[One-line verdict: "Good foundation, 6 fixes found"]
[Category breakdown — 6 horizontal bars]
   Skills ████████░░ 82   ← bar color = score color
[Suggestion cards — sorted by impact, top 3 shown]
   each: icon · bold issue · one-line why · [Fix] button
   "Show 3 more" expander                                ← progressive disclosure
[Sticky bottom bar: Fix My Resume →]                     ← one primary action
```

### 3.3 Builder `/builder` (wizard)

- One question per screen (cognitive load ≈ zero). Progress bar top, step X/6.
- Steps: Target role → Contact → Experience → Education → Skills → Review.
- Role step: autocomplete fed by O*NET roles (recognition over memory).
- Skills step: suggested-skill chips for chosen role, tap to add — user never types from memory.
- Every step auto-saves (localStorage before auth, DB after). Back never loses data.

### 3.4 Editor `/editor/[id]`

- Split view desktop: form left, live PDF preview right. Mobile: tabbed (Edit / Preview).
- Debounced re-score (800ms after typing stops) → score chip in header ticks up/down live.
- Suggestions panel collapsible on right — visible but never blocking (progressive disclosure).

---

## 4. Performance budget (fast = feature)

- LCP < 2.0s, CLS < 0.05, INP < 200ms — measured on 4G mobile, not your laptop.
- Landing JS bundle < 150KB gzipped. Heavy stuff (PDF preview, editor) = dynamic `import()` only on their routes.
- Images: `next/image`, AVIF/WebP, lazy below fold. Fonts self-hosted. Static pages pre-rendered (SSG). Vercel CDN default.
- Skeletons on every data fetch — perceived speed beats real speed.

## 5. Accessibility checklist (ship-blocking, not optional)

- Full keyboard navigation, visible `focus-visible` rings, skip-to-content link.
- Contrast ≥ 4.5:1 body / 3:1 large text. Score never conveyed by color alone (number + label always).
- Semantic landmarks (`nav/main/footer`), one `h1` per page, ordered heading levels.
- All inputs labeled, errors announced via `aria-live`. Gauge has `role="meter"` + `aria-valuenow`.
- `prefers-reduced-motion` respected globally.

---

## 6. Project structure (hierarchical, feature-first)

```
resume-website/
├── frontend/
│   ├── public/                      # favicons, og-images, robots.txt
│   ├── src/
│   │   ├── app/                     # Next.js App Router — routes ONLY, no logic
│   │   │   ├── layout.tsx           # root layout: fonts, providers, nav, footer
│   │   │   ├── page.tsx             # landing
│   │   │   ├── report/[id]/page.tsx
│   │   │   ├── builder/page.tsx
│   │   │   ├── editor/[id]/page.tsx
│   │   │   ├── templates/page.tsx
│   │   │   └── api/                 # route handlers (thin proxies to backend)
│   │   ├── features/                # ← feature-first: each folder self-contained
│   │   │   ├── score/
│   │   │   │   ├── components/      # ScoreGauge, CategoryBars, SuggestionCard
│   │   │   │   ├── hooks/           # useScore, useRescore
│   │   │   │   ├── api.ts           # fetchers for this feature only
│   │   │   │   └── types.ts
│   │   │   ├── builder/
│   │   │   │   ├── components/      # WizardShell, StepRole, StepSkills, SkillChips
│   │   │   │   ├── hooks/           # useWizardState (autosave)
│   │   │   │   └── steps.config.ts  # step order/config in data, not code
│   │   │   ├── editor/
│   │   │   │   ├── components/      # EditorForm, PdfPreview, SuggestionsPanel
│   │   │   │   └── hooks/           # useDebouncedRescore
│   │   │   ├── upload/              # DropZone, parse status
│   │   │   └── templates/           # TemplateGallery, TemplateCard
│   │   ├── components/
│   │   │   ├── ui/                  # design system atoms: Button, Input, Card,
│   │   │   │                        #   Toast, Skeleton, Modal, Badge, Accordion
│   │   │   └── layout/              # Nav, Footer, Container, Section
│   │   ├── lib/                     # api client, utils, analytics, constants
│   │   ├── styles/                  # globals.css, tokens.css (the variables above)
│   │   ├── types/                   # shared types (JSON Resume schema types)
│   │   └── config/                  # site metadata, nav items, feature flags
│   ├── tailwind.config.ts           # maps tokens.css vars into Tailwind theme
│   └── package.json
├── backend/                         # FastAPI (per PROJECT_PLAN.md)
│   ├── app/
│   │   ├── api/                     # routers: score, resume, suggest, auth
│   │   ├── core/                    # config, security, rate limiting
│   │   ├── services/                # parsing, scoring, rag, llm_router
│   │   ├── models/                  # SQLAlchemy + Pydantic schemas
│   │   └── main.py
│   └── tests/
├── ml/                              # JEPA track — isolated from product code
│   ├── pretraining/
│   ├── distillation/
│   └── eval/                        # benchmark vs SBERT baseline
├── data/                            # O*NET/ESCO ingestion scripts + normalized output
└── docs/                            # PROJECT_PLAN.md, this file, ADRs
```

**Structure rules**: route files stay dumb (compose features, no logic). A feature folder never imports from another feature — shared things get promoted to `components/ui` or `lib`. Design tokens live in ONE file (`tokens.css`); Tailwind reads them, so changing the brand color is a one-line edit.

---

## 7. Build order (frontend)

1. `tokens.css` + Tailwind config + `components/ui` atoms (Button, Input, Card, Toast, Skeleton) — the design system FIRST, pages second.
2. Layout shell: Nav, Footer, Container, Section.
3. Landing page (static, fastest win, validates the design system).
4. Upload flow + Score Report (the core product loop).
5. Builder wizard → Editor → Templates.
6. Polish pass: animations, empty states, error states, a11y audit, Lighthouse ≥ 95.
