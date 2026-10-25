---

description: "Task list for Feature 3: PaperPilot Web App"
---

# Tasks: PaperPilot Web App

**Input**: Design documents from `/specs/003-web-app/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/web-api.md,
contracts/engine-api.md, quickstart.md; ADR-0005, ADR-0006, ADR-0007

**Order (as requested)**: engine changes first, then the API, then the frontend. Within each
layer, tasks follow user-story priority: US1 (P1), US2 (P1), US3 (P2), US4 (P2), US5 (P2). A
story is complete when its frontend section's check passes; the engine and API sections also
end in runnable checks.

**Tests first**: every implementation task is preceded by a test task that must fail first.
Commit after each task: one commit per task, with a message naming the files it touches.

**Model safety**: no unit, API or component test may call the real LLM or the provider's key
endpoint. These guards enforce it:

- `tests/conftest.py` already blocks real OpenAI clients.
- T030 adds a guard for `llm._fetch_key_info`.
- Frontend tests mock `fetch` and never start the API.

Only `scripts/checkpoint_6_web.py` (real parts) and `scripts/usage.py` reach OpenRouter. Each
prints its planned requests and retries and enforces the Feature 2 budget rule: FAIL on
unplanned requests, FAIL if all requests exceed 2 × the plan.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 from spec.md; no label for Setup, Foundational and Polish

## Path Conventions

- Engine: `paperpilot/`; API adapter: `api/`; Python tests: `tests/` and `tests/api/`
- Frontend: `frontend/` (`app/`, `components/`, `lib/`, `tests/`, `e2e/`)
- Scripts: `scripts/`

---

## Phase 1: Setup

**Purpose**: dependencies and project scaffolding, all with exact pins (research R1).

- [X] T001 Add `fastapi==0.143.0`, `starlette==1.7.0`, `uvicorn==0.54.0`, `python-multipart==0.0.32` and `httpx==0.28.1` to `requirements.txt`. Install with `uv pip install -r requirements.txt`. Verify that `python -c "import fastapi.sse, multipart"` succeeds and `pytest` still passes. Commit `requirements.txt`.
- [X] T002 Scaffold `frontend/` by hand (no `create-next-app`, to keep the pins exact).
  - **Dependencies** in `frontend/package.json`:
    - `next 16.4.1` (16.4.0 has critical advisories; research R1), `react 19.3.0`, `react-dom 19.3.0`
    - `motion 14.1.0`, `react-pdf 11.0.0`
    - `clsx`, `tailwind-merge` and `lucide-react`, each at the newest version at least 14 days old
  - **devDependencies**:
    - `typescript 6.0.3`, `tailwindcss 4.3.3`, `@tailwindcss/postcss 4.3.3`
    - `@types/react 19.3.0`, `@types/react-dom 19.3.0`, `@types/node 26.6.5`
    - `vitest 5.0.3`, `@vitejs/plugin-react 6.1.2`, `jsdom 30.1.2`
    - `@testing-library/react 16.3.3`, `@testing-library/user-event 14.6.7`, `@testing-library/jest-dom` (newest at least 14 days old)
    - `@playwright/test 1.64.0`
  - **Scripts**:
    - `"dev": "next dev --hostname 127.0.0.1 --port 3000"`
    - `"start": "next start --hostname 127.0.0.1 --port 3000"`
    - `"build"`, `"typecheck": "tsc --noEmit"`, `"test": "vitest run"`, `"test:e2e": "playwright test"`
  - **Config files**: `frontend/tsconfig.json` (`strict: true`), `frontend/next.config.ts`, `frontend/postcss.config.mjs`.
  - Run `npm install` to create `frontend/package-lock.json`.
  - **Root `.gitignore`**: add `frontend/node_modules/`, `frontend/.next/`, `frontend/test-results/`, `frontend/playwright-report/`, `frontend/public/pdf.worker.min.mjs` and `frontend/.env.local`.
  - Commit these files.
- [X] T003 Create the design theme.
  - In `frontend/app/globals.css`, define the Tailwind v4 `@theme` tokens from research R12: `ink #07090D`, `panel #10141B`, `panel-2 #161B24`, `line #222A36`, `text #E6EAF0`, `muted #8B95A5`, `teal #5EEAD4`, `amber #F5B454`, `page #F4F1EA`, `highlight #F6D9A8`, `passage-text #1F2328`. Also define the `--font-heading`, `--font-body` and `--font-mono` variables, visible focus-ring utilities, and a `prefers-reduced-motion` base rule.
  - In `frontend/app/layout.tsx`, load Sora, Inter and JetBrains Mono with `next/font/google` and set `<html lang="en">` with `bg-ink text-text`.
  - Add a placeholder `frontend/app/page.tsx`. `npm run build` must succeed.
  - Commit the three files.
- [X] T004 Initialise shadcn/ui with the pinned CLI (`npx shadcn@4.21.4 init`, then `add button checkbox dialog sheet tooltip progress`) and restyle the generated components to the T003 tokens (dark only).
  - Files: `frontend/components.json`, `frontend/lib/utils.ts`, `frontend/components/ui/button.tsx`, `checkbox.tsx`, `dialog.tsx`, `sheet.tsx`, `tooltip.tsx`, `progress.tsx`.
  - Pin any packages the CLI adds to exact versions at least 14 days old.
  - Commit.
- [X] T005 [P] Configure the test runners.
  - `frontend/vitest.config.ts`: jsdom, the React plugin, setup file `frontend/tests/setup.ts` (jest-dom, a `matchMedia` mock, and a `fetch` guard that throws if a test calls the network without mocking).
  - `frontend/playwright.config.ts`: Chromium; `webServer: npm run dev` at `http://127.0.0.1:3000`; projects `desktop` (1280×800) and `phone` (375×740).
  - A trivial passing `frontend/tests/smoke.test.ts`.
  - Commit these files.
- [X] T006 [P] Add `frontend/scripts/copy-pdf-worker.mjs`. It copies `pdf.worker.min.mjs` from the `pdfjs-dist` version react-pdf depends on (6.3.289) into `frontend/public/`. Run it from the `postinstall` and `prebuild` scripts in `frontend/package.json`, and verify the copied file exists after `npm install`. Commit both files.

---

## Phase 2: Foundational (blocks every story)

**Purpose**: shared engine settings and errors, the API skeleton (readiness, CORS, trusted
hosts, error kinds), the frontend shell, and the boundary check.

- [X] T007 [P] Add failing tests to `tests/test_settings.py`:
  - `DAILY_REQUEST_LIMIT`: default 50; must be ≥ 1; an invalid value raises an error naming the variable and the value.
  - `FRONTEND_ORIGIN`: default `http://127.0.0.1:3000`.
  - `describe()` lists both.
- [X] T008 [P] Create failing tests in `tests/test_errors.py`:
  - `DailyLimitError` subclasses `LLMError` and has `used`, `limit` and `resets_at` (aware UTC).
  - `RateLimitedError` subclasses `LLMError`, has `until` and `daily`, and its message starts with `"rate limited until "`.
  - `PdfMissingError` subclasses `PaperPilotError` and has `paper_id`.
  - `LLMError` accepts an optional `reason` attribute (`busy`, `not_listed`, `unknown_model`, `bad_key`, `out_of_credits`, `cut_off`, `empty`, `timeout`, `unreachable`), defaulting to `None`.
- [X] T009 Implement `daily_request_limit` and `frontend_origin` in `paperpilot/config.py`, and the new errors and `LLMError.reason` in `paperpilot/errors.py`. T007 and T008 must pass, along with the full `pytest`.
- [X] T010 Create `tests/api/__init__.py` and `tests/api/conftest.py` with these fixtures:
  - `make_app`: builds the app through `api.main.create_app()` with a controllable loader event.
  - `client`: a `TestClient` used as a context manager so the lifespan runs. It waits until `/api/status` is `ready` and combines `library_env`, `fake_embedder`, `llm_env` and `fake_answers` with `RELEVANCE_THRESHOLD=0.0`.
  - `client_with_paper`: one generated paper added through the engine.
  - **Guard**: every test fails if the key value `llm_env` appears in any response body.
- [X] T011 Create failing tests in `tests/api/test_app.py`:
  - `GET /api/status` answers `loading` while the loader is blocked, then `ready`.
  - `GET /api/papers` answers `503 {"kind": "not_ready"}` while loading.
  - CORS: origin `http://127.0.0.1:3000` gets `access-control-allow-origin`; `http://evil.example` and `http://localhost:3000` don't.
  - A request with `Host: 192.168.1.20` is rejected by trusted hosts.
  - An unhandled exception in a test route returns `500 {"kind": "internal"}` with no traceback text.
  - A loader failure gives `state: "error"`.
- [X] T012 Implement the API skeleton so T011 passes:
  - `api/__init__.py`.
  - `api/main.py`: `create_app()`; a lifespan that starts a background thread running `store.load_model()`, a warm-up `library.search`, and `llm.refresh_usage()` once it exists (T032; guarded by `hasattr` until then); `CORSMiddleware` with the single `FRONTEND_ORIGIN`; `TrustedHostMiddleware` for `127.0.0.1` and `localhost`; a catch-all handler that logs server-side (key scrubbed) and returns `internal`.
  - `api/state.py`: the readiness state and the single-question guard.
  - `api/errors.py`: the `ApiError` type and the kind/status table from contracts/web-api.md.
  - `api/schemas.py`: shared Pydantic models.
  - `api/routes.py`: `GET /api/status`.
  - `api/__main__.py`: `python -m api` runs uvicorn on `127.0.0.1:8000`, never `0.0.0.0`.
  - Logging: also write to `<LIBRARY_DIR>/api.log` (gitignored under `data/`), with the key
    scrubbed and no prompts or answers logged.
- [X] T013 [P] Create failing tests:
  - `frontend/tests/api-client.test.ts`:
    - The base URL comes from `NEXT_PUBLIC_API_URL`, defaulting to `http://127.0.0.1:8000`.
    - JSON errors are parsed into a typed `ApiError` with its `kind`.
    - A network failure becomes `kind: "unreachable"`.
  - `frontend/tests/sse.test.ts`, for the `fetch`-stream SSE reader:
    - Events split across chunks.
    - Several events in one chunk.
    - `event:` and `data:` lines, with JSON data.
    - Ping comments ignored.
    - Stream end.
    - Abort.
- [X] T014 Implement `frontend/lib/types.ts` (types mirroring contracts/web-api.md), `frontend/lib/api.ts` and `frontend/lib/sse.ts` so T013 passes.
- [X] T015 [P] Add `frontend/tests/contrast.test.ts`.
  - It reads the colour tokens from `frontend/app/globals.css` and asserts a WCAG contrast of at least 4.5:1 for every pair in research R12: text on ink and on panel; muted on ink and on panel; teal and amber on ink and on panel; ink on teal and on amber; passage text on highlight and on page.
  - It also asserts that a fixture colour `#6B7280` on the panel fails, which proves the checker works (spec FR-031, SC-009).
- [X] T016 [P] Create failing tests in `frontend/tests/app-shell.test.tsx`:
  - `StatusGate` shows `GettingReady` while `/api/status` is `loading`.
  - It shows `Unreachable`, with how to start the server, when the fetch fails, and recovers on the next successful poll.
  - It renders its children when `ready`.
  - `Header` shows the PaperPilot name and a model chip such as "nemotron-3-ultra · free".
- [X] T017 Implement `frontend/components/app/StatusGate.tsx`, `frontend/components/app/Header.tsx`, `frontend/components/states/GettingReady.tsx` and `frontend/components/states/Unreachable.tsx`, and wire them in `frontend/app/layout.tsx`, so T016 passes. Status polls every 2 s while not ready and every 30 s once ready.
- [X] T018 Create `scripts/checkpoint_6_web.py` with the shared harness and part `boundary` (0 model requests).
  - **Shared harness**:
    - UTF-8 stdout and stderr.
    - Parts selected from the command line.
    - Per-part request plans, enforced with `scripts/request_budget.py budget_checks`.
    - Counts taken from each answer's `requests {planned, retries}`.
    - PASS/FAIL lines.
  - **Part `boundary`**:
    - `/api/status` is `ready`.
    - CORS allows `http://127.0.0.1:3000` and refuses other origins.
    - A foreign `Host` header is rejected.
    - TCP connections to the machine's LAN IP on ports 8000 and 3000 are refused, while `127.0.0.1` accepts (SC-012).
  - **Runnable check**: start both servers per quickstart and run `python scripts/checkpoint_6_web.py boundary`.

### Cross-site request protection (added 2026-10-24, analysis finding A1; before any write endpoint)

- [X] T072 Write failing tests for spec FR-002b and research R11.
  - **`tests/test_settings.py`:**
    - `FRONTEND_ORIGINS` is comma-separated and defaults to `("http://127.0.0.1:3000", "http://localhost:3000")`.
    - Blank entries are ignored; a value with no origin is invalid.
    - `describe()` lists it. Remove the single `FRONTEND_ORIGIN` tests.
  - **`tests/api/test_security.py`**, using a test-only `POST /api/echo` route that records whether it ran:
    - A cross-origin simple POST (`Origin: http://evil.example`, `Content-Type: text/plain`) gets `403 {kind: forbidden, reason: origin}`, and the route never runs.
    - The same applies to a multipart POST and to a GET from a foreign origin.
    - A preflight from a foreign origin is refused.
    - A write with no header, from an allowed origin or with no `Origin`, gets `403 {kind: forbidden, reason: header}`, and the route never runs. DELETE behaves the same.
    - A write with `X-PaperPilot: 1` from `http://127.0.0.1:3000` or `http://localhost:3000` runs and carries `access-control-allow-origin`.
    - A preflight from an allowed origin that asks for `x-paperpilot` is allowed.
    - Same-machine requests without `Origin` can read, and can write with the header.
  - **`tests/api/test_app.py`:** `http://localhost:3000` is now allowed. Read the origins from `FRONTEND_ORIGINS`.
  - **`frontend/tests/api-client.test.ts` and `frontend/tests/sse.test.ts`:** `apiPost`, `apiDelete` and `postEventStream` send `X-PaperPilot: 1`; `apiGet` doesn't need to.
- [X] T073 Make T072 pass:
  - `paperpilot/config.py`: replace `frontend_origin` with `frontend_origins` (`FRONTEND_ORIGINS`).
  - New `api/security.py`: the Origin guard and the `X-PaperPilot` check as one middleware, placed between trusted hosts and CORS.
  - `api/main.py`: CORS allows the origin list and the headers `Content-Type` and `X-PaperPilot`.
  - `api/errors.py`: the `forbidden` kind.
  - `frontend/lib/api.ts` and `frontend/lib/sse.ts`: send `X-PaperPilot: 1` on every write.
  - `.env.example`: `FRONTEND_ORIGINS`.
- [X] T074 Extend checkpoint 6 part `boundary` in `scripts/checkpoint_6_web.py` (0 model requests):
  - Both default origins are allowed, and `http://evil.example` is refused with `403 forbidden`.
  - A cross-origin simple POST is refused with reason `origin`.
  - A write without the header is refused with reason `header`.
  - **Runnable check:** with both servers running, `python scripts/checkpoint_6_web.py boundary`.

**Checkpoint**: `pytest`, `npm --prefix frontend test` and checkpoint 6 `boundary` pass.

**Every later write** (T034–T048 tests and checkpoint parts, T057/T058 uploads and deletes, T054
re-process) sends `X-PaperPilot: 1`. Tests must expect `403 forbidden` without it.

---

## Phase 3: Engine changes (by story priority)

### US1 (P1): progress while a question is answered

- [X] T019 [P] [US1] Create failing tests in `tests/test_service_events.py` (`answer_env`):
  - With `on_event`, a plain question emits `searching`, `reading` (`passages`, and `papers` as distinct papers), `generating` and `checking`, in that order.
  - With history, `rewriting` comes first.
  - Below the threshold, only `searching` is emitted, then the result.
  - With no passages, the same.
  - `on_event=None` behaves exactly as before.
  - Events never contain answer text.
- [X] T020 [P] [US1] Add failing tests to `tests/test_llm.py`:
  - With `on_retry`, a 429 followed by success calls it once with `RetryNotice(attempt=1, max_attempts=4, wait_seconds=3.0, reason="rate_limited")` before the sleep.
  - Timeout, 5xx and error-in-200 cases report the reasons `timeout`, `server_error` and `provider_error`.
  - First-try success never calls it.
- [X] T021 [US1] Implement `RetryNotice` and the `on_retry` parameter in `paperpilot/llm.py`, and `on_event` in `paperpilot/service.py`, forwarding retries as `retry_wait` events. T019, T020 and the full `pytest` must pass.

### US2 (P1): stored PDFs, highlight geometry, attach with layout, passage views

- [X] T022 [P] [US2] Create failing tests in `tests/test_ingest_layout.py`, using generated PDFs; extend `write_pdf` in `tests/conftest.py` to place hyphenated line breaks and two-page paragraphs.
  - `parse_pdf` keeps each block's word boxes and every page's size.
  - The new pure function `align_words(cleaned_words, raw_words)` handles hyphen joins (`repre-` + `sentation`) and falls back on a mismatch.
  - `chunk_sections` fills `Passage.regions` covering every word of each passage, including overlap words. Rectangles lie within the page box, one per line segment, and the pages are correct for a passage spanning two pages.
  - A split oversized paragraph covers only its own share of lines.
  - Table passages use their blocks' boxes.
  - `build_layout(paper, passages, settings)` returns the document described in data-model.md, including the chunk settings.
  - Passage texts and ids are unchanged compared with the existing tests.
  - `parse_pdf` sets `arxiv_id` from an `arXiv:2106.09685v2` stamp on page 1, and `None` without one.
- [X] T023 [US2] Implement the geometry in `paperpilot/ingest.py` (research R4, ADR-0006): word boxes on `Block`, `ParsedPaper.page_sizes` and `arxiv_id`, `align_words`, `Region`, `Passage.regions`, and `build_layout`. T022 and the full `pytest` must pass, which confirms the existing chunk output is unchanged.
- [X] T024 [P] [US2] Create failing tests in `tests/test_library_pdfs.py` (`library_env`, `fake_embedder`, `make_pdf`).
  - **Adding:** `add_paper` copies the PDF to `<LIBRARY_DIR>/pdfs/<id>.pdf` and writes `<id>.layout.json` atomically. Outcome `added`, highlights `exact`.
  - **Known content, PDF stored:** returns `already_present` without calling `parse_pdf` (spy).
  - **Known content, no PDF** (stored PDF removed): returns `pdf_attached` and never calls `embed_passages` (spy). The layout is written when the ids and texts match. A mismatch (chunk setting changed through env) writes no layout but writes a `.layout-mismatch` marker, with highlights `mismatch`.
  - **Viewing:**
    - `get_passage` returns regions for a laid-out paper.
    - It returns `layout=None` with reason `no_pdf`, or with reason `mismatch` and `can_reprocess=True`.
    - It never calls `parse_pdf`.
    - It raises for an unknown passage id.
  - **Files:** `pdf_path` raises `PdfMissingError` or `UnknownPaperError`. `delete_paper` removes the PDF, layout and marker.
  - **Re-processing** with `reprocess_paper`:
    - Success: replaces the passages only after embedding succeeds, clears the marker, returns outcome `reprocessed`.
    - Embedding failure: the old passages stay intact.
- [X] T025 [US2] Implement the stored PDFs, `attach_pdf`, `get_passage`, `pdf_path`, `reprocess_paper` and the PDF/layout removal on delete in `paperpilot/library.py`, plus `store.write_lock` held by upsert and delete in `paperpilot/store.py` (research R3, R14). T024 and the full `pytest` must pass.
- [X] T026 [US2] Create `scripts/checkpoint_6_geometry.py` (0 model requests, no embedding).
  - For each PDF in `papers/` (or given paths), it runs `parse_pdf`, `chunk_sections` and `build_layout`.
  - It prints, per paper, the share of passages with word-level regions, those that fell back to line boxes, and those without regions.
  - PASS if at least 90% of passages across the 5 test papers have word-level regions (the SC-002 proxy).
  - **Runnable check**: `python scripts/checkpoint_6_geometry.py`.

### US3 (P2): ingest progress, per-paper stats, arXiv ID

- [X] T027 [P] [US3] Add failing tests to `tests/test_store.py`: `embed_passages(texts, on_progress=cb)` calls `cb(done, total)` after each batch, with `done` increasing and ending at `total`. Without a callback the behaviour is unchanged.
- [X] T028 [P] [US3] Create failing tests in `tests/test_library_stats.py`:
  - `add_paper(on_progress=cb)` reports `parsing`, `chunking`, `embedding` (percent rising to 100) and `ready`, in that order.
  - An attach reports `mapping` then `ready`.
  - `already_present` reports only `ready`.
  - `list_papers()` fills `text_passages`, `table_passages`, `section_count`, `arxiv_id`, `has_pdf` and `highlights` (`exact`, `mismatch` or `no_pdf`).
  - `arxiv_id` is read from the stored page-1 passages when there is no layout, covering papers ingested before this feature.
- [X] T029 [US3] Implement batch progress in `paperpilot/store.py`, and the `on_progress` phases plus the extended `PaperSummary` in `paperpilot/library.py`, so T027, T028 and the full `pytest` pass.

### US5 (P2): request accounting and the long-wait rule (ADR-0007)

- [X] T030 [P] [US5] Create failing tests in `tests/test_llm_usage.py`, and add an autouse guard in `tests/conftest.py` that replaces `llm._fetch_key_info` with a stub that raises unless a test overrides it.
  - **Counting:**
    - Every attempt, first or retry, increments the day's row in `<LIBRARY_DIR>/usage.sqlite3`.
    - A new UTC day starts at 0 (clock injected through `llm._utcnow`).
    - 20 threads × 5 increments gives exactly 100.
    - Two processes (multiprocessing spawn) × 25 increments gives exactly 50.
  - **Pre-check:** at the limit, `generate()` raises `DailyLimitError` with zero fake-client calls.
  - **Refreshing:**
    - `refresh_usage()` adopts `free_model_daily_requests {used, limit}` from the stubbed key info with source `provider`.
    - A stub failure keeps the local count with source `local`.
    - With a non-OpenRouter provider, the key endpoint is skipped.
  - **Reporting:** `usage()` gives `remaining` and `resets_at` as the next 00:00 UTC.
- [X] T031 [P] [US5] Add failing tests to `tests/test_llm.py`, for FR-023a–c:
  - **Long waits:**
    - `Retry-After: 120` raises `RateLimitedError` after exactly one request, with the message "rate limited until …" and a correct `until`.
    - `Retry-After: 60` is retried.
  - **`X-RateLimit-Reset` values:**
    - A reset in the past is ignored, giving a 2.0 s backoff.
    - A reset beyond 48 h is ignored, giving backoff.
    - A reset given in seconds instead of milliseconds is ignored, giving backoff.
    - A valid reset 30 s ahead gives a 30 s wait.
  - **Daily classification:** `daily=True` when `X-RateLimit-Limit` equals the daily limit, or when the refreshed stub shows `remaining 0`; `False` for a per-minute limit of 20.
  - **Logging:** the WARNING retry log includes the raw `X-RateLimit-Reset` value.
  - **Reasons:** every terminal `LLMError` carries a `reason`.
- [X] T032 [US5] Implement the usage database, `usage()`, `refresh_usage()` (OpenRouter `GET /api/v1/key` through `httpx` with a 10 s timeout and the key only in the `Authorization` header), the daily pre-check, the long-wait rule, the 48-hour reset check, the raw header in logs, and the `LLMError.reason` values, all in `paperpilot/llm.py`. T030, T031 and the full `pytest` must pass, which shows Features 1–2 are unaffected.
- [X] T033 [US5] Create `scripts/usage.py` (0 model requests). It calls `llm.refresh_usage()` and prints `used / limit`, `remaining`, `resets_at` in UTC and local time, and the source, never the key.
  - **Runnable check**: run `python scripts/usage.py`, then `python scripts/checkpoint_4_answer.py us5 secrets` (0 requests), then the full `pytest`.

**Checkpoint (engine)**: full `pytest` passes; `checkpoint_6_geometry.py` passes; `usage.py` matches the provider's figure.

---

## Phase 4: API (by story priority)

### US1: ask with progress

- [X] T034 [P] [US1] Create failing tests in `tests/api/test_ask.py`, reading the stream through `TestClient`.
  - **Answered question:**
    - `POST /api/ask` streams `progress` events (`searching`, `reading`, `generating`, `checking`), then a final `answer`.
    - The answer has every field in contracts/web-api.md, including `verified`, `papers_read`, `requests {planned, retries}` and `usage`.
    - No answer text appears in any event before `answer`.
  - **Answers that aren't errors:**
    - Not-found arrives as an `answer` event with `not_found` and `fallback_reason`, and `verified=false`.
    - A held-back reply (cites [9] of 1) arrives as an `answer` with `rejected_answer`, a warning and `verified=false`.
  - **Validation before the stream:** `empty_question` (422), `unknown_paper` (404) and `not_ready` (503) are returned as plain JSON.
  - **One at a time:** a second ask while one is running gets `409 busy_question`.
  - **Retry waits:** a fake `generate` that calls `on_retry` produces a `retry_wait` event.
- [X] T035 [US1] Implement `POST /api/ask` in `api/routes.py`. The question runs in the threadpool, and its events are bridged through `loop.call_soon_threadsafe` onto an `asyncio.Queue` in the new `api/streams.py`.
  - The answer models go in `api/schemas.py`; `verified`, `papers_read` and the `requests` delta come from `llm.request_counts()`.
  - The single-question guard comes from `api/state.py`.
  - T034 must pass.
- [X] T036 [US1] Add part `ask` to `scripts/checkpoint_6_web.py` (plan: 1 request).
  - It streams "What is LoRA?" from the running API and prints each event, the answer, citations, `verified`, the timings and the request counts.
  - PASS if: the answer has valid citations only; `verified` is consistent with them; and no `progress` event carries text.
  - **Runnable check**: `python scripts/checkpoint_6_web.py ask`.

### US2: passages and PDFs

- [X] T037 [P] [US2] Create failing tests in `tests/api/test_passages.py`:
  - `GET /api/passages/{id}` returns the PassageView with layout regions for a laid-out paper.
  - It returns `layout:null` with `layout_reason:"no_pdf"`, or with `"mismatch"` and `can_reprocess:true`.
  - An unknown id gives `404 unknown_passage`.
  - The endpoint never parses (spy on `ingest.parse_pdf`).
  - `GET /api/papers/{id}/pdf` returns `200 application/pdf` inline with the stored bytes. `pdf_missing` and `unknown_paper` give 404.
- [X] T038 [US2] Implement both endpoints in `api/routes.py`, with their models in `api/schemas.py`, so T037 passes.
- [X] T039 [US2] Add part `viewer` to `scripts/checkpoint_6_web.py` (0 requests).
  - It takes the passages from part `ask`'s answer when `ask` ran, otherwise from `POST /api/search` (added in T047) for "What is LoRA?".
  - For each passage it fetches `/api/passages/{id}` and `/api/papers/{paper}/pdf`.
  - PASS if: every PDF opens and the cited page is within `page_count` (SC-001); and at least 90% of passages have regions on their cited page (SC-002). It reports passages without regions with their reason.
  - **Runnable check**: `python scripts/checkpoint_6_web.py ask viewer`.

### US3: library, uploads, jobs

- [X] T040 [P] [US3] Create failing tests in `tests/api/test_papers_jobs.py`:
  - **Listing:** `GET /api/papers` returns cards with every field and `total_passages`.
  - **Uploading:**
    - `POST /api/papers` with two PDFs returns two job ids.
    - `GET /api/jobs/events` streams `queued → parsing → chunking → embedding (percent) → ready` for each, processed one at a time.
    - `GET /api/jobs` returns the snapshot.
  - **Duplicates and attach:**
    - The same content under another name ends `ready` with outcome `already_present`.
    - Known content without a stored PDF goes `queued → mapping → ready`, with outcome `pdf_attached` and highlights `exact`.
  - **Rejected files:** non-PDF bytes (`not_pdf`), more than the limit (`too_large`; set `api.jobs.MAX_UPLOAD_BYTES` small in the test), an empty-text PDF (`no_text`) and a corrupt PDF (`unreadable`) each create a `failed` job.
  - **Re-processing:** `POST /api/papers/{id}/reprocess` returns 202 and runs to `reprocessed`. A second one while it is queued gets `409 busy_job`.
  - **Deleting:** `DELETE /api/papers/{id}` returns `removed_passages`.
  - **Not blocking questions:** an ask completes while an ingest job is held at `embedding` (blocked through a fake-embedder event).
- [X] T041 [US3] Implement `api/jobs.py`: the job registry; the single ingest worker thread (FIFO); chunked upload reading that aborts above 25 MB; the `%PDF-` check; temporary files under `<LIBRARY_DIR>/tmp` removed after each job; and the fan-out of job events to SSE subscribers. Add the papers, jobs, reprocess and delete routes in `api/routes.py`, so T040 passes.
- [X] T042 [US3] Add part `library` to `scripts/checkpoint_6_web.py` (0 model requests).
  - **Attaching the existing papers:** it uploads every PDF in `papers/` and waits for the jobs. Each must end `pdf_attached` (highlights `exact`) or `already_present`, with the attach finishing within 10 s (SC-004).
  - **Rejected and duplicate uploads:**
    - A generated non-PDF must give `upload_invalid` with `not_pdf`.
    - A renamed copy of one paper must give `already_present` within 3 s.
  - **Optional new paper:** `--new-pdf PATH` adds a new paper. It must reach Ready within 60 s with at least 3 phase changes seen, and is then deleted.
  - **Runnable check**: `python scripts/checkpoint_6_web.py library`.

### US4: scope and follow-ups

- [X] T043 [P] [US4] Create failing tests in `tests/api/test_ask_scope.py`:
  - **Scope:** `paper_ids` limits every passage to those papers. An empty list gives `422 no_papers_selected`.
  - **History:** the history is passed to `ask()`; the answer's `standalone_question`, `rewrite_applied` and `rewrite_fallback_reason` come through.
  - **Invalid history:** a bad role or a turn longer than 20,000 characters gives `422 {"kind": "invalid_request"}`. Add `invalid_request` to the error table in `specs/003-web-app/contracts/web-api.md`.
- [X] T044 [US4] Implement the scope and history validation and the `invalid_request` mapping in `api/schemas.py` and `api/errors.py`, so T043 passes.
- [X] T045 [US4] Add part `scope` to `scripts/checkpoint_6_web.py` (plan: 3 requests).
  - **Scoped question:** BERT only, "What data was BERT pre-trained on?". Every passage must come from BERT.
  - **Follow-up:** "What is LoRA?", then "What are its limitations?" with history. The standalone question must name LoRA, and the citations must be valid.
  - **Runnable check**: `python scripts/checkpoint_6_web.py scope`.

### US5: usage, search, error kinds

- [X] T046 [P] [US5] Create failing tests in `tests/api/test_usage_errors.py`:
  - **Usage:** `GET /api/usage` returns `used`, `limit`, `remaining`, `resets_at` and `source`. It refreshes from the provider at most once per 30 s (spy on `refresh_usage` with an injected clock).
  - **Search:** `POST /api/search` returns ranked passages and makes no `generate` call.
  - **Each engine exception maps to its kind and fields, as an `error` event mid-stream:**
    - `DailyLimitError` → `daily_limit`
    - `RateLimitedError` → `rate_limited`, with `until` and `daily`
    - `LLMError` with reason `busy` or `timeout` → `model_busy`
    - `LLMError` with reason `not_listed`, `unknown_model`, `bad_key`, `out_of_credits`, `cut_off` or `empty` → `model_unavailable`
  - **No leaks:** across every endpoint and error, with the key set, no response contains the key, `Traceback` or the provider's message text.
- [X] T047 [US5] Implement the `/api/usage` (with a 30 s refresh throttle in `api/state.py`) and `/api/search` routes, and complete the exception mapping in `api/errors.py`, so T046 passes. After every question the API calls `llm.refresh_usage()` (throttled) before sending `answer`.
- [X] T048 [US5] Add parts `states` and `usage` to `scripts/checkpoint_6_web.py`, both 0 model requests.
  - **`states`** runs in-process with `TestClient` and a scripted fake LLM, so no server and no requests are needed. It shows every error and answer state the API can produce and asserts each kind and its safe fields:
    - not found, retry wait and model busy
    - daily limit (pre-check, zero `generate` calls) and rate limited (daily and not daily)
    - held back and uncited sentence
    - model unavailable
    - unknown passage
    - upload invalid
  - **`usage`** checks that `GET /api/usage` equals what `python scripts/usage.py` prints.
  - **Runnable check**: `python scripts/checkpoint_6_web.py states usage`.

**Checkpoint (API)**: full `pytest` passes; checkpoint 6 parts `boundary ask viewer library scope states usage` pass within the plan of 4 requests (cap 8).

---

## Phase 5: Frontend (by story priority)

### US1 (P1): ask and get a verified, cited answer

**Independent test**: with a mocked API, ask a question and see the progress steps, then the
revealed answer with numbered chips and the verified badge.

- [X] T049 [P] [US1] Create failing tests in `frontend/tests/reveal.test.ts`:
  - `splitSentences` in `lib/sentences.ts` matches the engine's rule: it keeps citations with their sentence, including after the full stop.
  - `revealPlan(sentenceCount)` in `lib/reveal.ts` returns delays: 40 ms apart, 160 ms per fade, chips after the last sentence and the badge last, with the total at most 450 ms for any length.
  - With reduced motion, every delay is 0.
- [X] T050 [P] [US1] Create failing tests in `frontend/tests/ask.test.tsx` (mocked `fetch` stream):
  - **Composer:** an empty question shows "Type a question first" and sends nothing. Enter sends and Shift+Enter adds a newline. The composer is disabled while answering.
  - **Progress:** `ProgressSteps` shows "Searching…", "Reading 6 passages from 2 papers…" and "Checking citations…" from the events, and no answer text appears before the `answer` event.
  - **Answer:** `AnswerView` renders a chip `[n]` per citation as a button, with an accessible name such as "Citation 1: LoRA, page 5". The "All citations verified" badge appears only when `verified` is true. The answer meta shows passages read, time and model. The not-found text is rendered exactly as received.
- [X] T051 [US1] Implement `frontend/lib/sentences.ts` and `frontend/lib/reveal.ts` so T049 passes.
- [X] T052 [US1] Implement the Ask screen so T050 passes:
  - `frontend/components/ask/Composer.tsx`, `ProgressSteps.tsx`, `AnswerView.tsx`, `CitationChip.tsx` and `VerifiedBadge.tsx`.
  - `frontend/lib/useAsk.ts`, a hook driving `POST /api/ask` through `lib/sse.ts`.
  - `frontend/app/page.tsx`.
  - The reveal uses `motion` with `useReducedMotion()` and `lib/reveal.ts`.
- [X] T053 [US1] Create `frontend/e2e/fake-backend.ts` (Playwright `page.route` fixtures replaying recorded `/api/*` JSON and SSE bodies from `frontend/e2e/fixtures/`) and `frontend/e2e/smoke.spec.ts` with test "US1 ask".
  - The test asks a question, sees the progress, then the answer with chips and the badge, with no answer text before the reveal.
  - **Story check**: `npm --prefix frontend test` and `npm --prefix frontend run test:e2e -- -g "US1"`.

### US2 (P1): open a citation in the source PDF

**Independent test**: activate chip [1] and see the cited page with the passage highlighted;
the fallback cases show the passage text.

- [X] T054 [P] [US2] Create failing tests in `frontend/tests/source-viewer.test.tsx`, mocking `react-pdf` to render a sized placeholder.
  - **Opening:** activating a chip by click or Enter opens `SourceViewer` with the title, section, "page 5 of 26" and the score.
  - **Highlights:**
    - `HighlightOverlay` places the regions scaled from points to pixels (`lib/geometry.ts`), and they are labelled for screen readers.
    - Regions on the next page appear after "Next page", with a "continues on page 6" note.
  - **Fallbacks:**
    - `layout:null` shows the passage text beside the page with "Exact location could not be marked".
    - A `mismatch` reason also offers "Re-process paper for exact highlights", which calls `POST /api/papers/{id}/reprocess` and shows the job's progress.
    - `no_pdf` shows the text and the "add the file again" hint.
  - **Controls:** "Open full PDF" links to `/api/papers/{id}/pdf#page=5` in a new tab. Escape closes the viewer and returns focus to the chip.
- [X] T055 [US2] Implement `frontend/components/source/SourceViewer.tsx`, `frontend/components/source/HighlightOverlay.tsx` and `frontend/lib/geometry.ts` so T054 passes.
  - react-pdf uses `/pdf.worker.min.mjs`, with the text and annotation layers off.
  - The viewer is a side panel on desktop and a full-screen sheet below 768 px.
- [X] T056 [US2] Add test "US2 viewer" to `frontend/e2e/smoke.spec.ts`, with a small generated PDF fixture in `frontend/e2e/fixtures/`. Clicking a chip must render the page with a visible highlight box, and the fallback fixture must show the passage text.
  - **Story check**: `npm --prefix frontend run test:e2e -- -g "US2"`; then, with both servers running, `python scripts/checkpoint_6_web.py ask viewer`.

### US3 (P2): add papers and watch them become searchable

**Independent test**: drop PDFs and watch the phases. Duplicates show as already present and
attaches show "Mapping highlights" then "PDF attached". The cards show their counts.

- [X] T057 [P] [US3] Create failing tests in `frontend/tests/library.test.tsx`:
  - **Adding files:** `DropZone` accepts drag-and-drop and the file chooser (several files) and posts the multipart request.
  - **Upload rows** (`UploadRow`):
    - Shows Parsing → Chunking → Embedding with a percentage → Ready.
    - Shows "Already in your library" with a link to the card.
    - Shows "Mapping highlights" → "PDF attached", or "PDF attached — exact highlights unavailable".
    - Each failure reason has friendly copy and a next step.
    - "Re-processed".
  - **Jobs:** `useJobs` uses `/api/jobs/events` and falls back to polling `/api/jobs` when the stream fails.
  - **Paper cards** (`PaperCard`):
    - Shows the title, passages (text and table), sections, pages and arXiv ID.
    - "Ask this paper" links to `/?paper=<id>`.
    - Delete opens a confirmation dialog, and cancel changes nothing.
  - **Header:** the library header reads "5 papers, 223 searchable passages" and "Embeddings run on this machine".
  - **Not shown:** no Summarize button and no Compare tab.
- [X] T058 [US3] Implement the Library screen so T057 passes: `frontend/app/library/page.tsx`, `frontend/components/library/DropZone.tsx`, `UploadRow.tsx`, `PaperCard.tsx` and `LibraryHeader.tsx`, and `frontend/lib/useJobs.ts`. Add Ask/Library navigation to `frontend/components/app/Header.tsx`.
- [X] T059 [US3] Add test "US3 library" to `frontend/e2e/smoke.spec.ts`: drop two fixture files and see the phases, an attach and a duplicate; then delete with confirmation.
  - **Story check**: `npm --prefix frontend run test:e2e -- -g "US3"` and `python scripts/checkpoint_6_web.py library`.

### US4 (P2): scope and follow-ups

**Independent test**: select one paper, ask, and see only that paper cited. A follow-up shows
"Searched as …", and "New conversation" clears the history.

- [X] T060 [P] [US4] Create failing tests in `frontend/tests/scope.test.tsx`:
  - **Scope panel** (`ScopePanel`):
    - Lists the ready papers with checkboxes and passage counts, and reads "Search scope · 2 of 5 papers".
    - The last selected paper can't be cleared; it explains why, and sending is disabled with none selected.
    - `?paper=<id>` preselects only that paper.
    - The selection persists in `localStorage`, wrapped in try/catch.
  - **Conversation:**
    - Follow-ups send the previous turns as `history`.
    - The answer shows `Searched as "…"` when `rewrite_applied`, and "Searched as typed" when the rewrite fell back.
    - "New conversation" clears the turns.
  - **Phone width:** the panel opens as an overlay sheet.
- [X] T061 [US4] Implement `frontend/components/library/ScopePanel.tsx`, `frontend/components/ask/Conversation.tsx` and `frontend/components/ask/SearchedAs.tsx`, and extend `frontend/lib/useAsk.ts` with history and selection, so T060 passes.
- [X] T062 [US4] Add test "US4 scope" to `frontend/e2e/smoke.spec.ts`: a scoped question, then a follow-up showing "Searched as".
  - **Story check**: `npm --prefix frontend run test:e2e -- -g "US4"` and `python scripts/checkpoint_6_web.py scope`.

### US5 (P2): every failure is designed and friendly

**Independent test**: each failure kind renders its designed state with no raw error text, and
the usage meter shows today's count.

- [X] T063 [P] [US5] Create failing tests in `frontend/tests/states.test.tsx`:
  - **NotFound:** the exact sentence, plus "Search all papers" (shown only when not all papers are selected; it re-asks with all) and "Rephrase more specifically" (focuses the composer).
  - **Busy:** `retry_wait` events give a live countdown and "attempt 2 of 4"; it uses fake timers and keeps counting through re-renders.
  - **ModelBusy:** all retries failed; the question text is kept, with "Try again".
  - **DailyLimit:** for example "50 / 50 free requests used today" and "Answers resume at 05:00", in the researcher's local time from `resets_at`. "Browse passages instead" calls `/api/search` and lists results with paper, section and page.
  - **RateLimited:** for a non-daily wait, "Try again at HH:MM" in local time.
  - **HeldBack:** the warning ("The model cited passage 7, but only 6 were provided…"). "View the unverified answer" reveals `rejected_answer`, labelled "Not verified", with the invalid numbers marked.
  - **UncitedFlag:** uncited sentences get a dotted underline and "1 sentence has no citation"; the badge still shows.
  - **Other states:**
    - ModelUnavailable names the configured model and points to settings, without the key.
    - PassageGone: a chip whose passage no longer exists shows "This passage is no longer in your library".
    - UploadInvalid shows its copy.
  - **Raw errors:** no component ever renders `error.message` from the network.
- [X] T064 [US5] Implement `frontend/components/states/NotFound.tsx`, `Busy.tsx`, `ModelBusy.tsx`, `DailyLimit.tsx`, `RateLimited.tsx`, `HeldBack.tsx`, `UncitedFlag.tsx`, `ModelUnavailable.tsx` and `PassageGone.tsx`, plus `frontend/lib/errorKinds.ts` (kind → component, with all copy owned here), and wire them into `AnswerView` and `useAsk`, so T063 passes.
- [X] T065 [P] [US5] Create failing tests in `frontend/tests/usage-meter.test.tsx`, then implement `frontend/components/app/UsageMeter.tsx` and wire it into `Header.tsx`:
  - It shows "Requests today 34 / 50".
  - It refreshes after each answer, from the answer's `usage`, and every 60 s.
  - The count turns amber when 5 or fewer requests remain.
  - At the limit it links to the daily-limit state.
  - The model chip shows "· free" for `:free` models.
  - Commit the test and the implementation together, test written first.
- [X] T066 [US5] Add tests "US5 states" to `frontend/e2e/smoke.spec.ts`, replaying the fixtures for not found, busy countdown, daily limit with browse passages, held back with the unverified answer, and server unreachable.
  - **Story check**: `npm --prefix frontend run test:e2e -- -g "US5"` and `python scripts/checkpoint_6_web.py states usage`.

---

## Phase 6: Polish and cross-cutting concerns

- [X] T067 [P] Extend `frontend/e2e/smoke.spec.ts` to run every story test in the `phone` project (375 px). Assert `document.documentElement.scrollWidth <= clientWidth` on the Ask, Library and state screens. Add a keyboard-only pass that completes US1–US4 with Tab, Enter, Space and Escape, with the focus ring visible (SC-008, FR-029, FR-030).
- [X] T068 [P] Add test "reduced motion" to `frontend/e2e/smoke.spec.ts`, using `page.emulateMedia({ reducedMotion: 'reduce' })`: the answer appears in one step. With motion, the text, chips and badge are all visible within 500 ms of the `answer` event, measured with `performance.now()` in the page (SC-011).
- [X] T069 [P] Add part `secrets` to `scripts/checkpoint_6_web.py` (0 requests). It runs `npm --prefix frontend run build`, then checks:
  - The key value is absent from `frontend/.next/`, from every response captured in this run and from the API log file (`<LIBRARY_DIR>/api.log`, configured in T012).
  - The only `NEXT_PUBLIC_*` variable in use is `NEXT_PUBLIC_API_URL`.
  - `git check-ignore` passes for `data/library/pdfs/x.pdf` and `data/library/usage.sqlite3`.
  - It prints PASS/FAIL only, never the key (SC-010).
- [ ] T070 [P] Add a "Web app" section to `docs/known-limitations.md`:
  - Localhost only, with no network access or sign-in yet.
  - Upload jobs are lost on restart, though the library is unaffected.
  - One upload at a time.
  - Highlights are tied to the chunk settings, and re-processing changes passage ids.
  - Usage covers only this key's free-model requests on OpenRouter; with other providers it is the local count only.
  - The units of `X-RateLimit-Reset` remain unconfirmed until a real 429.
  - The viewer renders one page at a time.
- [ ] T071 Run the full quickstart (`specs/003-web-app/quickstart.md`) and fix any drift in it:
  - The test commands: `pytest`, `npm --prefix frontend run typecheck`, `npm --prefix frontend test` and `npm --prefix frontend run test:e2e`.
  - Both servers, then `python scripts/checkpoint_6_web.py` with all parts (plan: 4 model requests, cap 8; check `scripts/usage.py` first).
  - `python scripts/checkpoint_6_geometry.py`.
  - Record the pass/fail results, the request totals, the timings and each SC result (SC-001–SC-013) in the PHR.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup** (T001–T006) → **Foundational** (T007–T018, then T072–T074) → **Engine** (T019–T033) → **API**
  (T034–T048) → **Frontend** (T049–T066) → **Polish** (T067–T071).
- Within each layer, stories go US1 → US2 → US3 → US4 → US5. A layer's story section depends only
  on the same story's sections in the lower layers and on Foundational. One exception: the US2
  API check T039 uses `/api/search` from T047 when part `ask` is skipped.

### Story dependencies

- **US1** needs T021 (engine events) → T035 (ask stream) → T052 (Ask screen).
- **US2** needs T023 and T025 (geometry, PDFs) → T038 → T055; its viewer opens from US1's chips.
- **US3** needs T029 (progress, stats) and T025 (attach) → T041 → T058.
- **US4** needs US1's ask path (T035, T052) → T044 → T061.
- **US5** needs T032 (accounting, long waits) and US1's ask path → T047 → T064 and T065.

### Within each story

- The test task comes first and must fail; then the implementation; then the runnable check.
- Files shared across stories are edited by sequential tasks, never in parallel:
  `paperpilot/library.py`, `paperpilot/llm.py`, `api/routes.py`, `api/schemas.py`,
  `scripts/checkpoint_6_web.py` and `frontend/e2e/smoke.spec.ts`.

### Parallel opportunities

- **Setup:** T005 and T006 (after T002).
- **Foundational:** T007 with T008; T013 with T015 and T016 (frontend, after T005).
- **Engine:** T019 with T020; T022 with T024 (test files); T027 with T028; T030 with T031.
- **API:** each story's test task [P] can be written alongside the previous story's
  implementation, since the test files differ.
- **Frontend:** T049 with T050; T063 with T065.
- **Polish:** T067, T068, T069 and T070.

## Parallel Example: Engine US5

```text
T030 tests/test_llm_usage.py + tests/conftest.py   (counter, pre-check, refresh)
T031 tests/test_llm.py                             (long waits, reset sanity, reasons)
→ then T032 paperpilot/llm.py
```

## Parallel Example: Frontend US1

```text
T049 frontend/tests/reveal.test.ts   (sentences, reveal timing)
T050 frontend/tests/ask.test.tsx     (composer, progress, answer view)
→ then T051 lib, T052 components
```

---

## Implementation Strategy

### MVP (US1 + US2, both P1)

1. Setup and Foundational: the API answers `/api/status`, and the boundary check passes.
2. Engine US1 and US2 → API US1 and US2 → Frontend US1 and US2: ask, see a verified answer, and
   open its citation with a highlight. Checkpoint parts `ask viewer` (1 request).

### Incremental delivery

3. US3: the library in the browser, including attaching the five existing PDFs.
4. US4: scope and follow-ups.
5. US5: every designed failure state and the usage meter.
6. Polish: phone width, keyboard, reduced motion, secrets, docs and the full quickstart run.

### Request plan for checkpoint 6

| Part | Planned model requests | Notes |
|---|---|---|
| boundary, viewer, library, states, usage, secrets | 0 | `states` runs in-process with the fake LLM |
| ask | 1 | "What is LoRA?" |
| scope | 3 | BERT-scoped question; "What is LoRA?" plus a follow-up (rewrite + answer) |
| **Full run** | **4** (cap 8) | retries are reported; check `scripts/usage.py` before running |

## Notes

- [P] tasks touch different files and depend on no incomplete task.
- Commit after each task, with a message naming its files and ending with the Co-Authored-By
  line.
- Never call the real LLM or the key endpoint from tests. If a test needs either, it is a
  checkpoint part.
- When a real 429 happens, read the raw `X-RateLimit-Reset` value in the WARNING log and record
  its units in research R8 (FR-023b).
