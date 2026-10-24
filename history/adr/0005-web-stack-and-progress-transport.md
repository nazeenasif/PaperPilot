# ADR-0005: Web Stack and Progress Transport

> **Scope**: Document decision clusters, not individual technology choices. Group related decisions that work together (e.g., "Frontend Stack" not separate ADRs for framework, styling, deployment).

- **Status:** Accepted
- **Date:** 2026-10-24
- **Feature:** 003-web-app
- **Context:** Constitution v1.3.0 (Principle IX) makes PaperPilot a web app.
  - **Constitution constraints:**
    - The frontend is Next.js, and a thin FastAPI backend exposes the `paperpilot` engine.
    - The engine stays the single source of logic.
    - The browser never calls the LLM.
  - **Spec requirements:**
    - Long operations show live progress: ingest phases with an embedding percentage, the steps
      of a question, and a countdown while the provider asks the engine to wait.
    - Answers appear only after their citations are checked.
    - Uploads must not block questions.
    - Both servers are reachable only from the same machine.
  - **Engine facts:**
    - The engine is synchronous Python.
    - Embedding is CPU-bound, taking tens of seconds per paper.
    - A question mostly waits on the network, 5–40 s on the free tier.
    - Loading the embedding model takes 20–30 s cold.

## Decision

- **Layout:** the `paperpilot` package stays at the repository root and gains no new modules.
  - `api/` is a FastAPI app. It translates HTTP into engine calls and engine exceptions into
    error kinds.
  - `frontend/` is a Next.js App Router project.
- **Backend:**
  - FastAPI 0.143.0 (Starlette 1.7.0) on uvicorn 0.54.0, with python-multipart for uploads.
  - Pins are the newest release at least 14 days old (research R1).
- **Frontend:**
  - Next.js 16.4.1, React 19.3.0 and TypeScript 6.0.3 in strict mode. 16.4.1 rather than the planned 16.4.0, which has critical advisories (research R1). TypeScript 7 isn't used
    because Next's in-process type checker can't load it.
  - Tailwind CSS 4.3.3 with a CSS-first `@theme` built from `docs/design/`.
  - shadcn/ui components and motion 14.1.0.
  - No AI or LLM SDKs.
- **Progress transport:** Server-Sent Events, using FastAPI's built-in `EventSourceResponse`
  (since 0.135, with a 15 s keep-alive).
  - `POST /api/ask` streams `progress`, then `retry_wait`, then a final `answer` or `error`
    event. The browser reads it with `fetch` and a stream reader.
  - `GET /api/jobs/events` streams upload and re-process job changes.
  - `GET /api/jobs` returns a snapshot for page load, reconnects and polling.
- **Concurrency:**
  - One dedicated ingest worker thread processes jobs in order, one at a time.
  - Questions run in FastAPI's threadpool, and only one question runs at a time (`409
    busy_question`).
  - The engine reports progress through plain callbacks (`on_progress`, `on_event`,
    `on_retry`), bridged to asyncio with `call_soon_threadsafe`.
  - A process-wide lock guards library writes; searches don't take it.
- **Readiness:** the lifespan starts a background thread that loads the model, opens the library,
  runs a warm-up search and refreshes usage.
  - `GET /api/status` always answers, with `loading`, `ready` or `error`.
  - Endpoints that need the library answer `503 not_ready` until loading finishes.
- **Errors:** every error is a JSON `{kind, …safe fields}`, and the UI owns all wording. Stack
  traces, provider messages and the key never reach the browser.
- **Network boundary:**
  - uvicorn runs with `--host 127.0.0.1`, and Next.js with `--hostname 127.0.0.1`. Both are set
    explicitly because Next defaults to all interfaces.
  - `CORSMiddleware` allows only `FRONTEND_ORIGIN` (default `http://127.0.0.1:3000`).
  - `TrustedHostMiddleware` accepts only the hosts `127.0.0.1` and `localhost`.
  - The browser calls the API directly at `NEXT_PUBLIC_API_URL`; there is no Next.js proxy.

## Consequences

### Positive

- The engine keeps all logic. `api/` stays thin enough to review at a glance, and engine tests
  keep covering behaviour.
- The busy countdown reaches the browser within a second of the engine starting a wait. One
  streaming mechanism serves questions and uploads, and no new dependency was added.
- A question stays responsive during ingest: search is about 0.1 s and shares only the CPU with
  embedding.
- "Getting ready" can be told apart from "server unreachable", because the server accepts
  connections while it loads.
- Same-machine-only access and a single allowed origin keep the papers and the free-request
  quota away from other devices, with no authentication to build.
- Exact pins and a committed lockfile make checkpoint runs reproducible.

### Negative

- SSE over `POST` can't use the browser's `EventSource`, so the frontend needs its own small
  stream reader and its tests.
- Upload jobs live in memory and are lost on a server restart, although the library itself stays
  consistent because engine writes are atomic.
- One ingest worker means several large PDFs queue behind each other.
- Two dev servers and two toolchains (uv and npm) to run. The page must be opened at
  `127.0.0.1:3000`, because `localhost:3000` is a different origin and is rejected by CORS.
- Threads and a write lock add concurrency reasoning that the scripts never needed.
- Moving to network access later, which is out of scope here, will need authentication and a
  CORS and host review. This ADR doesn't cover that.

## Alternatives Considered

- **Alternative A: polling only.**
  - Simpler server code.
  - But 0.5–1 s lag, and many requests during a 10–40 s answer.
  - Kept only as the fallback (`GET /api/jobs`).
- **Alternative B: WebSockets.**
  - Two-way communication isn't needed.
  - More connection-lifecycle code, and harder to test with `TestClient`.
- **Alternative C: `sse-starlette` or hand-rolled `StreamingResponse`.** Unnecessary since
  FastAPI 0.135; the built-in version already handles keep-alive and headers.
- **Alternative D: a process pool or a task broker (Celery or RQ) for ingest.**
  - A process pool would load the embedding model twice.
  - A broker is disproportionate for one local user (Principle VIII).
- **Alternative E: a Next.js rewrite proxy (`/api/*` → FastAPI) to avoid CORS.**
  - Same-origin requests and no CORS configuration.
  - Rejected because dev-server proxying can buffer or compress SSE streams, which would freeze
    the countdown.
- **Alternative F: Streamlit or a server-rendered Python UI.** Excluded by constitution v1.3.0
  and unable to deliver the designed states and source viewer.
- **Alternative G: the newest version of every package.** Rejected because several were 1–2 days
  old on the planning date.

## References

- Feature Spec: specs/003-web-app/spec.md (FR-001–FR-003, FR-006, FR-010, FR-017, FR-022,
  FR-029–FR-032; clarification Q1 and the localhost refinement)
- Implementation Plan: specs/003-web-app/plan.md (Key Decisions 1–3, 9–12)
- Contracts: specs/003-web-app/contracts/web-api.md, specs/003-web-app/contracts/engine-api.md
- Related ADRs: ADR-0003 (LLM Boundary and Retry Policy), ADR-0006 (Citation Highlight
  Geometry), ADR-0007 (LLM Request Accounting and Long Waits)
- Evaluator Evidence: specs/003-web-app/research.md R1–R3, R9–R12;
  history/prompts/003-web-app/5-plan-paperpilot-web-app.plan.prompt.md
