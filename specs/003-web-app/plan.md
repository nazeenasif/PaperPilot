# Implementation Plan: PaperPilot Web App

**Branch**: `003-web-app` | **Date**: 2026-10-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-web-app/spec.md`

## Summary

A local web app over the existing engine. A thin **FastAPI** adapter in `api/` exposes the
`paperpilot` package. It loads the embedding model and library once, in a background thread
started by the lifespan, and reports `loading` / `ready`. It runs uploads on a single ingest
worker and streams their phases. It streams a question's progress and retry countdowns as
**Server-Sent Events**, using FastAPI's built-in SSE, then sends the checked answer. A **Next.js**
frontend in `frontend/` (App Router, TypeScript, Tailwind v4 theme from `docs/design/`,
shadcn/ui, motion) renders the Ask and Library screens and every designed failure state.

The engine gains five capabilities, all inside the package:

- **Stored PDFs:** a copy of each PDF, with a "PDF attached" path for papers already in the
  library.
- **Highlight geometry:** word-level passage geometry recorded at ingest, so the source viewer
  (react-pdf) can draw exact highlights.
- **Progress callbacks:** progress reporting from ingest and from `ask()`.
- **Request accounting:** a shared SQLite daily counter, reconciled with OpenRouter's
  `free_model_daily_requests` figure.
- **Long waits:** a "no retry on long waits" rule, with a 48-hour sanity window for
  `X-RateLimit-Reset`.

Both servers bind to 127.0.0.1, and the API accepts only the frontend's origin. Details are in
[research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (engine and API); TypeScript 6.0.3 on Node 24.18 (frontend)

**Primary Dependencies**:
- **Python:** FastAPI 0.143.0 (Starlette 1.7.0), uvicorn 0.54.0, python-multipart 0.0.32.
- **Frontend:** Next.js 16.4.0, React 19.3.0, Tailwind CSS 4.3.3, shadcn CLI 4.21.4, motion
  14.1.0, react-pdf 11.0.0 (pdfjs-dist 6.3.289).
- **Pinning:** every pin is the newest release at least 14 days old, verified 2026-10-24 (R1).

**Storage**:
- Unchanged: the Feature 1 ChromaDB store.
- New, all under the gitignored `data/library/`: `pdfs/<id>.pdf`, `pdfs/<id>.layout.json` and
  `usage.sqlite3`.

**Testing**:
- **Engine and API:** pytest, with FastAPI `TestClient`, the fake LLM and the fake embedder.
- **Frontend:** Vitest 5.0.3 with Testing Library and jsdom.
- **End to end:** Playwright 1.64.0, as a smoke test against a fake backend.
- **Real runs:** `scripts/checkpoint_6_web.py` with a printed request plan.

**Target Platform**: Windows 10/11 desktop, local CPU, Chromium-based browser on the same machine

**Project Type**: web application (engine package + API adapter + frontend)

**Performance Goals**:
- Search step under 2 s after ready (SC-005).
- A 20-page PDF reaches Ready in under 60 s (SC-004).
- Duplicate outcome in under 3 s; attach with highlight mapping in under 10 s.
- Answer reveal under 500 ms (SC-011).
- Countdown events within 1 s of the engine starting a wait.

**Constraints**:
- 127.0.0.1 only, and CORS limited to one origin.
- No model calls from the browser and no secrets in the browser.
- No answer text before citation checks.
- 4.5:1 contrast and reduced motion respected.
- Free tier: 20 requests/min and 50/day, counted per UTC day.

**Scale/Scope**: one researcher, tens of papers (~50 passages each), one question at a time, uploads processed one by one

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle (v1.3.0) | Check | Status |
|---|---|---|
| I. Plain, typed code | Engine/API Python 3.12, typed with docstrings, no LangChain; frontend strict TypeScript, no AI/LLM SDKs (only react, next, motion, react-pdf, UI libs) | ✅ |
| II. Modular package, single LLM boundary | No new package modules: geometry in `ingest`, PDF/attach/passage views in `library`, write lock and batch progress in `store`, usage accounting and key endpoint in `llm` (the only module talking to the provider), progress events in `service`. `api/` is a thin adapter outside the package with no retrieval/prompt/citation/LLM logic; frontend reaches the engine only through the API | ✅ |
| III. OpenAI-compatible LLM, free by default | Unchanged; the key endpoint is OpenRouter-specific and used only when `LLM_PROVIDER=openrouter` (other providers fall back to the local count) | ✅ |
| IV. Local embeddings, persistent store | Model loaded once at API start; store schema unchanged; no re-embedding for duplicates or attached PDFs | ✅ |
| V. Grounded answers (NON-NEGOTIABLE) | Answer sent only after `review_reply()`; `verified` only without invalid citations; exact `NOT_FOUND` shown unchanged; held-back text shown labelled unverified | ✅ |
| VI. Secrets and data hygiene | Key stays server-side, never in responses, logs or the bundle (`NEXT_PUBLIC_*` holds only the API URL); PDFs, layouts and usage DB under gitignored `data/`; checkpoint scans the built frontend for the key | ✅ |
| VII. Testable checkpoints, measured quality | pytest (engine + API), Vitest, Playwright smoke, `checkpoint_6_web.py` with request plan and `--simulate` failure states; retrieval/prompts unchanged, so no eval-harness run is required | ✅ |
| VIII. Simplicity, small commits | Built-in SSE (no sse-starlette), one ingest thread (no broker), SQLite in `llm.py` (no new module), no ESLint, no fuzzy-match fallback; each new dependency maps to a requirement | ✅ |
| IX. Visible grounding in a web interface | Clickable chips open the PDF page with highlights, title/section/page; progress for ingest and questions; designed states for every failure kind; localhost only | ✅ |

**Post-design re-check (after Phase 1)**: unchanged. The contracts add parameters to existing
engine functions and no module. `api/` maps engine exceptions to error kinds without
interpreting answers.

## Project Structure

### Documentation (this feature)

```text
specs/003-web-app/
├── plan.md
├── research.md            # R1–R14
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── web-api.md         # HTTP + SSE contract for the frontend
│   └── engine-api.md      # engine additions the API relies on
├── checklists/requirements.md
└── tasks.md               # /sp.tasks
```

### Source Code (repository root)

```text
paperpilot/                    # engine (existing modules only)
├── config.py                  # + daily_request_limit, frontend_origin
├── errors.py                  # + DailyLimitError, RateLimitedError, PdfMissingError
├── ingest.py                  # + word boxes, page sizes, arxiv_id, Passage.regions, build_layout()
├── store.py                   # + embed progress callback, write lock
├── library.py                 # + PDF copy/attach (with mapping)/reprocess/delete, extended PaperSummary, pdf_path(), get_passage()
├── llm.py                     # + usage SQLite counter, refresh_usage(), daily pre-check, long-wait rule, on_retry
└── service.py                 # + on_event progress callback

api/                           # NEW: thin FastAPI adapter (Principle II)
├── __init__.py
├── main.py                    # app, lifespan (background load), CORS, trusted hosts, routers
├── state.py                   # readiness, single-question guard
├── jobs.py                    # upload jobs, ingest worker thread, job event fan-out
├── routes.py                  # endpoints from contracts/web-api.md
├── schemas.py                 # pydantic response/request models
└── errors.py                  # engine exception → {kind, …} mapping

frontend/                      # NEW: Next.js App Router
├── app/
│   ├── layout.tsx             # fonts (next/font), header with model chip + usage meter
│   ├── globals.css            # Tailwind v4 @theme tokens from docs/design
│   ├── page.tsx               # Ask screen
│   └── library/page.tsx       # Library screen
├── components/
│   ├── ask/                   # Composer, Conversation, AnswerView, CitationChip, VerifiedBadge, ProgressSteps
│   ├── source/                # SourceViewer (react-pdf page + highlight overlay)
│   ├── library/               # DropZone, UploadRow, PaperCard, ScopePanel
│   ├── states/                # NotFound, Busy (countdown), DailyLimit, HeldBack, UncitedFlag, Unreachable, GettingReady
│   └── ui/                    # shadcn/ui components (generated, restyled)
├── lib/                       # api.ts (typed client), sse.ts (fetch-stream reader), sentences.ts, usage.ts
├── tests/                     # Vitest component tests
├── e2e/                       # Playwright smoke + fake-backend fixtures
├── public/pdf.worker.min.mjs  # copied from pdfjs-dist at build
├── package.json / package-lock.json
└── next.config.ts, vitest.config.ts, playwright.config.ts, tsconfig.json (strict)

tests/
├── test_ingest_layout.py      # NEW: word boxes, hyphen alignment, regions, layout file
├── test_library_pdfs.py       # NEW: PDF copy, attach + mapping (match and mismatch), reprocess, delete, summaries, get_passage
├── test_llm_usage.py          # NEW: counter, concurrency, provider refresh, daily pre-check, long waits
├── test_service_events.py     # NEW: ask() progress events
└── api/                       # NEW: TestClient tests per endpoint, SSE streams, errors, CORS, hosts

scripts/
└── checkpoint_6_web.py        # NEW: real end-to-end over HTTP with request plan; --simulate
```

**Structure Decision**: The package stays at the root, unchanged in shape. `api/` is a sibling
package imported as `api.main:app`, and `frontend/` is a standalone Node project. API tests live
under the existing `tests/` tree so one `pytest` run covers the engine and the API.

## Key Decisions (rationale in research.md)

ADRs: [ADR-0005 Web Stack and Progress Transport](../../history/adr/0005-web-stack-and-progress-transport.md) (1–3, 9–12),
[ADR-0006 Citation Highlight Geometry](../../history/adr/0006-citation-highlight-geometry.md) (4–5),
[ADR-0007 LLM Request Accounting and Long Waits](../../history/adr/0007-llm-request-accounting-and-long-waits.md) (7–8; amends ADR-0003).

1. **Exact pins:** each is the newest release at least 14 days old. TypeScript 6.0.3 rather
   than 7, and react-pdf's own pdfjs-dist version (R1).
2. **Progress transport:** SSE, using FastAPI's built-in support. `POST /api/ask` streams
   progress, retry waits and then the answer. Jobs have an event stream plus a snapshot for
   polling and reconnects (R2).
3. **Threads:** one ingest worker thread, questions in the threadpool, and a store write lock
   (R3).
4. **Highlights:** word-level geometry recorded at ingest and kept in per-paper layout files.
   Attaching a PDF builds its layout in the same ingest job, as a "Mapping highlights" step
   (parse and chunk, no embedding), written only if every passage id and text matches. On a
   mismatch, the viewer offers "Re-process paper for exact highlights". Fuzzy matching was
   rejected (R4).
5. **Viewer:** react-pdf renders a single page with a DOM highlight overlay, and a local pdf.js
   worker (R5).
6. **Answer reveal:** progress events while `ask()` runs, then a staggered entrance capped at
   450 ms, instant with reduced motion (R6).
7. **Request accounting:** a SQLite daily counter in `llm.py`, counting retries, safe for
   concurrent writers, per UTC day. OpenRouter's `free_model_daily_requests` is preferred, and a
   pre-check blocks requests at the limit (R7).
8. **Long waits:** no retry when the wait is longer than 60 s. `X-RateLimit-Reset` is trusted
   only within 48 hours, and the raw header is logged to confirm its units (R8).
9. **Readiness:** the lifespan starts background loading, and `/api/status` always answers
   (R9).
10. **Error contract:** errors are sent as kinds, and the UI owns all wording (R10).
11. **Network:** both servers bind to 127.0.0.1, CORS allows only the frontend origin, and
    trusted hosts are enforced. There is no proxy (R11).
12. **Design tokens:** a Tailwind v4 `@theme` with measured contrast and a token contrast test
    (R12).

## Phase plan (for /sp.tasks)

1. **Setup:** Python deps, the Next.js scaffold with pinned versions, the Tailwind theme, the
   shadcn init, and test runners.
2. **Foundational engine work:** errors and config, usage counter and long-wait rule (FR-023a–c,
   tests first), progress callbacks, the store write lock, and the API skeleton (status,
   readiness, CORS, hosts, error mapping).
3. **US1, ask:** the ask SSE endpoint, the answer view, chips, the badge, progress steps and the
   reveal.
4. **US2, source viewer:** geometry at ingest, layout files, `get_passage`, PDF serving, and the
   viewer overlay.
5. **US3, library:** PDF copy and attach, extended summaries, upload jobs and their stream, and
   the Library screen.
6. **US4, scope and follow-ups:** the scope panel, history, "Searched as", and new
   conversation.
7. **US5, failure states:** every designed state, the usage meter, daily limit, browse passages,
   unreachable, and getting ready.
8. **Polish:** accessibility pass (keyboard, 375 px, contrast test), the Playwright smoke test,
   `checkpoint_6_web.py`, quickstart run, and known limitations.

## Risks

1. **Geometry alignment gaps:** unusual PDFs (ligature glyphs, rotated text) can break word
   alignment. Mitigation: fall back to the block's line boxes, then to the FR-013 text fallback.
   SC-002 is measured on the five test papers in checkpoint 6.
2. **Concurrent CPU load:** embedding during a question slows the search step. Mitigation: one
   ingest worker and a short critical section; SC-005 is measured with an ingest running.
3. **Provider changes:** if OpenRouter changes the key endpoint or the header semantics, usage
   falls back to the local count, and the 48-hour rule keeps a bad reset value harmless. Units
   are confirmed on the first real 429.

## Complexity Tracking

No constitution violations to justify.

FR-018, as amended on 2026-10-24, builds the highlight layout inside the attach job ("Mapping
highlights": parse and chunk, no embedding), verified against the stored passages.
`get_passage` never parses, so opening a citation is always a plain read.
