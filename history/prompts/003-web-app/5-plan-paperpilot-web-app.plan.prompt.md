---
id: 5
title: Plan PaperPilot Web App
stage: plan
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 003-web-app
branch: 003-web-app
user: Nazeen Asif
command: /sp.plan
labels: ["plan", "fastapi", "nextjs", "sse", "react-pdf", "geometry", "usage-counter", "versions"]
links:
  spec: specs/003-web-app/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/003-web-app/plan.md
 - specs/003-web-app/research.md
 - specs/003-web-app/data-model.md
 - specs/003-web-app/quickstart.md
 - specs/003-web-app/contracts/web-api.md
 - specs/003-web-app/contracts/engine-api.md
tests:
 - none (planning); one OpenRouter key-endpoint read (not a model request)
---

## Prompt

/sp.plan Plan Feature 3 (003-web-app). Repository layout: keep the paperpilot package at the root; add api/ (FastAPI app) and frontend/ (Next.js, App Router, TypeScript, Tailwind CSS, shadcn/ui, Framer Motion). Verify current stable versions of Next.js, FastAPI and the PDF viewer library before pinning.

Decisions to research and justify:
- Upload progress: Server-Sent Events vs polling for ingest phases; background processing must not block questions.
- Citation highlighting: passages are cleaned text (hyphens rejoined, reference markers removed), so finding them in the PDF text layer by string match will often fail. Evaluate storing each passage's page-level bounding boxes at ingest (PyMuPDF already has block coordinates) versus fuzzy text matching in the viewer. Prefer accuracy; record the trade-off.
- PDF viewer: pdf.js-based (e.g. react-pdf) rendering a page with a highlight overlay.
- Answer reveal: progress steps from the backend while ask() runs, then the verified answer with a <500 ms entrance animation, instant under prefers-reduced-motion.
- Daily request counter: SQLite, reset at the provider's reset time, retries included, provider headers preferred.
- Startup: load the embedding model and library once in FastAPI's lifespan; report readiness to the UI.

Testing: API tests with FastAPI's test client and the fake LLM (never the real API); frontend component tests (Vitest + Testing Library); one end-to-end smoke test (Playwright) against a fake backend. Checkpoint scripts for real end-to-end runs must print their LLM request counts.

Constraints: both servers bind 127.0.0.1; CORS limited to the frontend origin; the design tokens and fonts from docs/design/ become a Tailwind theme.

Suggest which decisions deserve ADRs.

## Response snapshot

Versions read from npm/PyPI on 2026-10-24; pinned the newest release ≥ 14 days old (Next 16.4.0,
React 19.3.0, FastAPI 0.143.0 + Starlette 1.7.0, react-pdf 11.0.0 with its pdfjs-dist 6.3.289,
motion 14.1.0, Tailwind 4.3.3, TypeScript 6.0.3 instead of 7 for Next's checker, Vitest 5.0.3,
Playwright 1.64.0). OpenRouter docs: daily count per UTC day; X-RateLimit-* only on 429 (units
undocumented); GET /api/v1/key returns free_model_daily_requests — read live: used 34/50,
matching the session estimate. Decisions: built-in FastAPI SSE (0.135+) for ask and jobs plus a
snapshot endpoint; one ingest worker thread and a store write lock; word-level geometry at ingest
in per-paper layout files (lazy rebuild for attached PDFs, verified by passage id/text; fuzzy
matching rejected); react-pdf single page + overlay; progress events then a ≤ 450 ms staggered
reveal; usage SQLite in llm.py (BEGIN IMMEDIATE, WAL) preferring the provider figure and
pre-checking the limit; no retry when the wait > 60 s, reset trusted within 48 h; lifespan starts
background loading so /api/status answers during load; error kinds not messages; 127.0.0.1 +
CORS + trusted hosts, no proxy (SSE buffering); Tailwind v4 @theme with measured contrast (muted
#8B95A5 6.1:1; #6B7280 fails). Constitution check I–IX passes; no new package modules. The
agent-context script only added a BOM to CLAUDE.md; reverted.

## Outcome

- ✅ Impact: plan, research (R1–R14), data model, web and engine contracts, quickstart.
- 🧪 Tests: none (planning).
- 📁 Files: see list.
- 🔁 Next prompts: ADRs (web stack and transport; citation geometry; ADR-0003 amendment for long waits and request accounting); then /sp.tasks.
- 🧠 Reflection: the provider's key endpoint makes the usage meter authoritative; headers alone could never have worked because successful responses carry none.

## Evaluation notes (flywheel)

- Failure modes observed: update-agent-context.ps1 wrote only a BOM to CLAUDE.md.
- Graders run and results (PASS/FAIL): constitution check PASS (pre and post design)
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
