# Research: PaperPilot Web App (Feature 3)

Date: 2026-10-24. Every version below was read from the npm registry or PyPI on this date
(`npm view`, `https://pypi.org/pypi/<name>/json`); provider facts from OpenRouter's limits
documentation and one call to its key endpoint (not a model request).

## R1. Versions and pinning policy

- **Decision**: pin exact versions, choosing the newest release that is **at least 14 days old**
  (published on or before 2026-10-10). Several projects released in the last 48 hours (Next.js
  16.4.3, FastAPI 0.162.0, Starlette 1.10.0, sse-starlette 3.5.1, motion 14.6.0); a two-week
  margin avoids yanked or hot-fixed releases and supply-chain surprises at no real cost.

  | Package | Latest (date) | Pinned (date) | Note |
  |---|---|---|---|
  | **Python** | | | |
  | fastapi | 0.162.0 (10-23) | **0.143.0** (10-08) | built-in SSE since 0.135.0 (R2) |
  | starlette | 1.10.0 (10-24) | **1.7.0** (09-23) | via FastAPI (`>=0.46.0`); pinned to keep the resolver off today's release |
  | uvicorn | 0.54.0 (09-25) | **0.54.0** | already installed |
  | python-multipart | 0.0.32 (06-04) | **0.0.32** | needed for file uploads |
  | **Node** (Node 24.18.0, npm 11.6.2 installed; Next needs ≥ 20.9) | | | |
  | next | 16.4.3 (10-23) | **16.4.0** (10-06) | App Router |
  | react, react-dom | 19.3.1 (10-14) | **19.3.0** (09-09) | |
  | typescript | 7.0.2 (07-08) | **6.0.3** (04-16) | TS 7 (Go compiler) has no JS compiler API; Next's in-process type check needs an experimental flag for it — not worth it |
  | tailwindcss, @tailwindcss/postcss | 4.3.3 (07-16) | **4.3.3** | v4 CSS-first `@theme` (R12) |
  | shadcn (CLI) | 4.22.1 (10-18) | **4.21.4** (10-07) | copies component source into the repo; not a runtime dependency |
  | motion | 14.6.0 (10-22) | **14.1.0** (10-09) | Framer Motion's current package (`motion/react`); `framer-motion` is the same release line |
  | react-pdf | 11.0.0 (09-10) | **11.0.0** | depends on `pdfjs-dist` **6.3.289** exactly; do not pin pdfjs-dist separately (worker must match) |
  | vitest | 5.0.5 (10-15) | **5.0.3** (09-30) | |
  | @vitejs/plugin-react | — | **6.1.2** (10-05) | |
  | jsdom | 30.1.3 (10-15) | **30.1.2** (10-04) | |
  | @testing-library/react | 16.3.3 (08-27) | **16.3.3** | |
  | @testing-library/user-event | 14.6.8 (10-13) | **14.6.7** (09-02) | |
  | @playwright/test | 1.64.1 (10-14) | **1.64.0** (10-07) | |
  | @types/react, @types/react-dom | — | **19.3.0** | |
  | @types/node | — | **26.6.5** (10-09) | |

- **Alternatives**: newest of everything (rejected: day-old releases); caret ranges (rejected:
  constitution VIII and reproducible checkpoints favour exact pins; `package-lock.json` is
  committed). ESLint is not added: `tsc --noEmit` plus tests cover correctness, and Next 16 no
  longer runs a linter during build.
- **Re-check**: before `/sp.implement` installs anything, re-run the two queries; if a pinned
  release has been deprecated, take the next one that is ≥ 14 days old.

## R2. Progress transport: Server-Sent Events (FastAPI built-in) with a polling fallback

- **Decision**: one-way **Server-Sent Events** for both ingest jobs and questions, using
  FastAPI's built-in `fastapi.sse.EventSourceResponse` / `ServerSentEvent` (added in 0.135.0;
  sends a keep-alive ping every 15 s and sets `Cache-Control: no-cache`), so no `sse-starlette`
  dependency.
  - **Questions**: `POST /api/ask` answers with an event stream (`progress`, `retry_wait`,
    `answer` or `error`). The browser reads it with `fetch()` and a stream reader (EventSource
    cannot POST). The stream ends after the final event.
  - **Uploads**: `POST /api/papers` (multipart, several files) returns job ids at once;
    `GET /api/jobs/events` streams phase changes for all jobs; `GET /api/jobs` returns the
    current snapshot, used on page load, after a reconnect, and as the polling fallback.
- **Rationale**: progress is server → browser only; SSE gives sub-second updates (the busy
  countdown needs the retry wait the moment it starts) without WebSocket machinery; the built-in
  support removes a dependency. A snapshot endpoint makes reconnects trivial: the UI never
  depends on having seen every event.
- **Alternatives**: polling only (simpler, but 0.5–1 s lag and many requests during a 10–40 s
  answer; kept as the fallback); WebSockets (two-way not needed, more code, harder to test);
  `sse-starlette` (unnecessary since FastAPI 0.135).

## R3. Background work must not block questions

- **Decision**: ingest jobs run on **one dedicated worker thread** (a FIFO queue: one paper at a
  time, because embedding saturates the CPU); each question runs in FastAPI's threadpool
  (`ask()` is synchronous and mostly waits on the network). The engine reports progress through
  plain callbacks; the API bridges them into the asyncio event stream with
  `loop.call_soon_threadsafe` onto an `asyncio.Queue`. Library writes (upsert, delete, PDF
  attach) take a process-wide lock in `store`; searches read without it.
- **Rationale**: a question during ingest only shares the CPU with embedding — search is
  ~0.1 s — so questions stay responsive (spec US3 scenario 1). One worker keeps memory flat and
  progress readable.
- **Alternatives**: a process pool (would load the embedding model twice); Celery/RQ (a broker
  for one local user violates Principle VIII); asyncio-only (embedding is CPU-bound and blocks
  the loop).

## R4. Citation highlighting: page geometry recorded at ingest (chosen) vs fuzzy text match

Passages are cleaned text: words hyphenated across lines are rejoined, whitespace normalised,
blocks reordered by column bands, and 40 overlap words carried from the previous passage. A
string search in the PDF's text layer therefore fails on hyphen joins, ligatures (`ﬁ`),
two-column order, footnote markers and the overlap that starts in another block.

- **Decision**: record **word-level geometry at ingest** and serve it per passage.
  - `ingest.parse_pdf` keeps, for every text block, its page and the boxes of its words
    (`page.get_text("words")`, grouped by block number), plus each page's size.
  - Cleaned words are aligned to raw words greedily: a raw word ending in `-` followed by a raw
    word whose concatenation equals the cleaned word consumes both; any other mismatch ends the
    alignment for that block and falls back to the block's line boxes.
  - `chunk_sections` already knows which blocks and word ranges form each passage (including
    overlap words, which the model also read); it records them, and the word boxes are merged
    into one rectangle per line per page.
  - The result is written to a per-paper **layout file** next to the stored PDF
    (`<library>/pdfs/<paper_id>.layout.json`: page sizes plus `passage_id → [{page, rects}]`),
    because ChromaDB metadata holds only scalars and the store need not change.
  - The viewer draws the rectangles of the cited page over the rendered page (scaled from PDF
    points to pixels); rectangles on the next page are shown when the reader turns to it, with a
    "continues on page N+1" note.
- **Papers added before this feature** (PDF attached later, spec US3 scenario 4, FR-018 as
  amended 2026-10-24): the attach job stores the PDF and then, **in the same ingest-worker job**,
  runs a "Mapping highlights" step: the deterministic parse and chunk steps (no embedding, about
  1–2 s) regenerate the passages with their regions, and the layout file is written only if
  every regenerated passage id and text equals the stored one (same set, same order). On a
  mismatch — typically because chunk settings changed since the paper was embedded — no layout
  is written, the job still ends as "PDF attached" with `layout: "mismatch"`, and the viewer
  opens the cited page without a highlight, shows the passage text alongside and offers
  **"Re-process paper for exact highlights"** (FR-018a): a normal ingest job from the stored PDF
  (parse, chunk, embed, layout) that replaces the paper's passages only after the new ones are
  embedded, under the store write lock, so a failure leaves the old passages in place.
  Re-processing can change passage ids; answers already on screen keep their passage numbers but
  a chip whose passage no longer exists opens the "passage no longer in the library" state.
  *Superseded design*: building the layout lazily on the first citation view (rejected after
  planning: it hid work in a read request, made the first citation slow, and could not be shown
  as progress).
- **Rationale**: exact, deterministic, unit-testable in Python with generated PDFs, and cheap
  (geometry is a by-product of the parse that already runs). "Highlighted text is exactly what
  the model read" stays true, including overlap words.
- **Trade-offs recorded**: more ingest code (alignment, layout file, attach-time mapping,
  re-process job); layout becomes stale if chunk settings change (detected by the id/text check;
  the viewer falls back and offers re-processing);
  table passages are highlighted by their blocks' boxes (tables are flattened text, so the box
  is the table area — acceptable).
- **Alternative rejected as primary — fuzzy matching in the viewer**: normalise the pdf.js text
  layer and the passage (lowercase, strip hyphens and markers) and search with an edit-distance
  window. No ingest change, but it is approximate, slow on long pages, hard to test, and fails on
  column order; measured accuracy would decide SC-002 rather than design. Not implemented as a
  second fallback either (Principle VIII): when geometry is missing the honest fallback is the
  passage text beside the page.

## R5. PDF viewer: react-pdf (pdf.js) with an overlay

- **Decision**: `react-pdf` 11.0.0 renders **one page** (`<Document>` + `<Page>`, text layer and
  annotation layer off), loaded from `GET /api/papers/{id}/pdf`. A positioned layer of
  `<mark>`-styled rectangles (amber, semi-transparent, outlined) sits over the canvas; scale =
  rendered width ÷ page width in points. The pdf.js worker is served from the same
  `pdfjs-dist` version react-pdf depends on (copied into `public/` at build, no CDN). The viewer
  shows title, section, "page 5 of 26", score, prev/next page buttons, and "Open full PDF"
  (the API URL with `#page=N`, opened in a new tab with the browser's own viewer).
- **Rationale**: pdf.js is the de-facto renderer; react-pdf is the maintained React wrapper; a
  single page keeps memory and time low; the overlay is plain DOM, so it is accessible
  (`aria-label` on the highlight region) and testable.
- **Alternatives**: `<iframe>` of the browser's viewer (no highlight overlay, no control);
  `pdfjs-dist` directly (more lifecycle code); commercial viewers (licensing).

## R6. Answer reveal: backend progress events, then a verified answer with a < 500 ms entrance

- **Decision**: `service.ask()` accepts an optional `on_event` callback and reports
  `rewriting`, `searching`, `reading` (passages, papers), `generating`, `retry_wait` (seconds,
  attempt, max attempts, reason) and `checking`. The API forwards these as SSE `progress` and
  `retry_wait` events; the final `answer` event carries the full checked `Answer`. No answer text
  is sent before `review_reply()` has run (spec FR-011).
- **Front end**: the answer component splits the text into sentences (same rule as the
  engine's sentence splitter) and uses `motion` with a stagger: sentences 40 ms apart, 160 ms
  fade each, chips after the last sentence, badge last; the total is capped at 450 ms by
  shrinking the stagger for long answers. `useReducedMotion()` (and the CSS media query) renders
  everything at once.
- **Alternatives**: token streaming (rejected in clarification: unverified text on screen);
  CSS-only animation (fine, but `motion` is already the constitution's stack and handles the
  cap and reduced motion cleanly).

## R7. Daily request counter: SQLite plus the provider's own figure

**Verified provider facts** (OpenRouter limits documentation, 2026-10-24):

- Free models: 20 requests/minute; 50/day with fewer than 10 credits purchased, 1,000/day with
  at least 10. The daily count is per **UTC day** (reset 00:00 UTC — the spec's expectation is
  confirmed).
- `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` are sent **only on 429
  errors** and describe the limit that was hit; successful responses carry none. Units of
  `X-RateLimit-Reset` are not documented (R8).
- `GET /api/v1/key` returns `free_model_daily_requests: {used, limit, remaining}` (plus
  `is_free_tier`). A call on 2026-10-24 returned `used 34, limit 50, remaining 16` — matching
  this project's own estimate of ~33 from the day's checkpoint runs. This call is not a model
  request and does not count.

**Decision**:

- `llm.py` (the only module that talks to the provider, Principle II) owns request accounting.
  A small SQLite database at `<LIBRARY_DIR>/usage.sqlite3` holds one row per UTC day: `used`,
  `limit`, `source` (`local` or `provider`), `updated_at`. Every attempt (first or retry)
  increments `used` inside `BEGIN IMMEDIATE` with WAL mode and a 5 s busy timeout, so the app and
  a script running at the same time never lose a count (FR-025).
- **The provider's figure is preferred**: `llm.refresh_usage()` reads `/api/v1/key` and
  overwrites the day's `used`/`limit` with the provider's numbers (source `provider`). It runs at
  server start, after each question, after each 429, and on `GET /api/usage` at most once every
  30 s. Rate-limit headers on a 429 also update the row when they describe the daily limit.
  If the endpoint fails, the local count stands (source `local`).
- **Pre-check**: before any request, `llm.generate()` raises `DailyLimitError` (subclass of
  `LLMError`, with the reset time) when `used >= limit` — so neither the app nor a script spends a
  request that cannot succeed (FR-026, SC-007).
- `DAILY_REQUEST_LIMIT` setting, default 50 (the provider's limit replaces it when known).
- **Alternatives**: headers only (impossible — successful responses have none); local count
  only (blind to requests made elsewhere with the same key); a separate `usage` module (needs a
  constitution amendment for one table; kept in `llm.py`); a JSON file (no safe concurrent
  increments).

## R8. Long provider waits and X-RateLimit-Reset (FR-023a–FR-023c)

- **Decision**: in `retry_wait`, a hinted wait (Retry-After or X-RateLimit-Reset) longer than
  `MAX_WAIT_SECONDS` (60) no longer gets capped and retried: `generate()` raises
  `RateLimitedError(until, daily)` at once — readable message "rate limited until <time>" — after
  exactly one request (SC-013). `daily` is true when the 429's `X-RateLimit-Limit` equals the
  known daily limit or a refreshed `/api/v1/key` shows `remaining == 0`. X-RateLimit-Reset is
  trusted only if it resolves to a time in the future and within 48 hours; otherwise it is
  ignored and the 2/4/8 s backoff applies. It is read as epoch milliseconds (current behaviour);
  a value in seconds would resolve to 1970 and be ignored safely. The raw header value is
  included in the WARNING retry log line so its unit can be confirmed from the first real 429,
  then recorded here.
- **Tests (fake client)**: long Retry-After; Retry-After exactly 60 s (retried); reset in the
  past; reset beyond 48 h; reset given in seconds; daily vs per-minute classification; exactly
  one request counted.
- **ADR**: amends ADR-0003's retry policy.

## R9. Startup and readiness

- **Decision**: the FastAPI `lifespan` starts a background thread that loads the embedding model
  (`store.load_model()`), opens the library and runs one warm-up search, then marks the app
  `ready`; it also calls `llm.refresh_usage()`. The server accepts connections immediately, so
  `GET /api/status` can answer `{"state": "loading"}` (the UI's "Getting ready" state) instead of
  the browser seeing a refused connection. Endpoints that need the library return
  `503 {kind: "not_ready"}` until ready. Load failures set `state: "error"` with a safe reason.
- **Rationale**: model loading takes 18–30 s cold (Feature 2 measurements); blocking the
  lifespan would make "Getting ready" indistinguishable from "server unreachable".

## R10. Error contract: kinds, not messages

- **Decision**: every API error body is `{kind, ...safe fields}`; the UI owns all wording
  (spec FR-022: no raw error text, stack traces or provider messages). Kinds: `not_ready`,
  `empty_question`, `no_papers_selected`, `unknown_paper`, `daily_limit` (`used`, `limit`,
  `resets_at`), `rate_limited` (`until`), `model_busy` (all retries failed), `model_unavailable`
  (model not listed / 404 / 401 / misconfigured — no key value), `upload_invalid` (`reason`:
  `not_pdf`, `too_large`, `no_text`, `unreadable`, `password`), `pdf_missing`, `internal`. A
  catch-all handler logs the exception server-side (key scrubbed) and returns `internal`.
- Not-found and held-back answers are **not errors**: they are normal `answer` events with
  `not_found`, `fallback_reason`, `warning` and `rejected_answer`.

## R11. Localhost only and CORS (FR-002a, SC-012)

- **Decision**: `uvicorn api.main:app --host 127.0.0.1 --port 8000` and
  `next dev --hostname 127.0.0.1 --port 3000` (both explicit; Next's default is all
  interfaces). `CORSMiddleware(allow_origins=[FRONTEND_ORIGIN])`, default
  `http://127.0.0.1:3000`, methods GET/POST/DELETE, no credentials. `TrustedHostMiddleware`
  allows only `127.0.0.1` and `localhost` (defence against DNS rebinding). The browser calls the
  API directly at `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` (not a secret). The quickstart
  says to open `http://127.0.0.1:3000` (`localhost:3000` is a different origin).
- **Alternative**: a Next.js rewrite proxy (`/api/*` → FastAPI) to avoid CORS — rejected because
  dev-server proxying can buffer or compress SSE streams, which would break the countdown.

## R12. Design tokens and fonts

- **Decision**: Tailwind v4 CSS-first theme in `frontend/app/globals.css` (`@theme`): colours
  `ink #07090D`, `panel #10141B`, `panel-2 #161B24`, `line #222A36`, `text #E6EAF0`,
  `muted #8B95A5`, `teal #5EEAD4`, `amber #F5B454`, `page #F4F1EA`, `highlight #F6D9A8`;
  fonts `--font-heading` Sora, `--font-body` Inter, `--font-mono` JetBrains Mono loaded with
  `next/font/google` (downloaded at build and self-hosted — no runtime requests to Google).
  shadcn/ui components are restyled through these tokens (dark theme only).
- **Contrast (measured, WCAG formula)**: text on panel 15.3:1; teal on ink 13.5:1; amber on ink
  11.0:1; ink on teal buttons 13.5:1; ink on amber chips 11.0:1; muted `#8B95A5` on panel 6.1:1;
  passage text `#1F2328` on highlight 11.6:1 and on page 14.0:1. **Rule**: no text colour darker
  than `muted` on dark surfaces (`#6B7280` measures 3.8:1 and fails FR-031). A Vitest check
  computes these ratios from the token file so a token change cannot silently break SC-009.

## R13. Testing strategy (no real model calls in automated tests)

- **Engine (pytest)**: existing fixtures (fake embedder, scripted LLM, generated PDFs) cover the
  new engine parts: layout geometry and alignment, PDF store/attach/delete, progress callbacks,
  usage counter (concurrent increments from threads and two processes), long waits, daily
  pre-check.
- **API (pytest + FastAPI `TestClient`)**: `api/` tests with the fake LLM and fake embedder;
  SSE streams read through the client; every error kind; CORS and trusted-host behaviour; upload
  limits; never the real API (the existing autouse guard blocks real clients).
- **Frontend (Vitest + Testing Library + jsdom)**: answer view states (verified, uncited,
  held back, not found), citation chips, scope selector, upload rows, usage meter, countdown,
  reduced motion, token contrast.
- **End-to-end smoke (Playwright, Chromium)**: the real frontend against a **fake backend**
  (`page.route` fixtures replaying recorded API and SSE responses) — ask, open a citation,
  upload with phases, daily-limit state; 375 px viewport; keyboard-only path.
- **Real runs**: `scripts/checkpoint_6_web.py` drives the running API over HTTP (ask, follow-up,
  scoped question, citation geometry, upload, duplicate, PDF attach) with a planned request
  budget printed per part (planned + retries, scripts/request_budget.py); failure states are
  demonstrated with the fake LLM via `--simulate` so they cost no requests.

## R14. Stored PDFs

- **Decision**: `<LIBRARY_DIR>/pdfs/<paper_id>.pdf` (under the gitignored `data/` folder,
  Principle VI). `library.add_paper` copies the file after a successful store;
  `library.attach_pdf` handles the "already in library, no PDF" case (store the PDF, then map
  highlights with the id/text check); `library.reprocess_paper` rebuilds a paper from its stored
  PDF; `delete_paper` removes the PDF and layout file. Uploads are checked server-side: ≤ 25 MB (read in chunks, abort when
  exceeded), `%PDF-` magic bytes, then the engine's own errors for unreadable, password and
  no-text files.
