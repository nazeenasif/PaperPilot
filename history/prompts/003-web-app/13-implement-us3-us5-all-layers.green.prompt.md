---
id: 13
title: Implement US3 and US5 in all layers
stage: green
date: 2026-10-25
surface: agent
model: claude-opus-5-5
feature: 003-web-app
branch: 003-web-app
user: Nazeen Asif
command: /sp.implement
labels: ["library", "uploads", "jobs", "failure-states", "request-accounting", "long-wait", "usage-meter"]
links:
  spec: specs/003-web-app/spec.md
  ticket: null
  adr: history/adr/ (ADR-0007 request accounting)
  pr: null
files:
 - paperpilot/llm.py
 - paperpilot/errors.py
 - paperpilot/ingest.py
 - scripts/usage.py
 - scripts/checkpoint_6_web.py
 - api/jobs.py
 - api/routes.py
 - api/main.py
 - api/state.py
 - api/errors.py
 - api/schemas.py
 - specs/003-web-app/contracts/web-api.md
 - specs/003-web-app/tasks.md
 - frontend/app/library/page.tsx
 - frontend/app/layout.tsx
 - frontend/components/library/ (LibraryScreen, DropZone, UploadRow, PaperCard, LibraryHeader)
 - frontend/components/states/ (StateCard, NotFound, Busy, ModelBusy, DailyLimit, RateLimited, HeldBack, UncitedFlag, ModelUnavailable, PassageGone, TurnFailure)
 - frontend/components/app/UsageMeter.tsx
 - frontend/components/app/Header.tsx
 - frontend/components/ask/AskScreen.tsx
 - frontend/components/ask/AnswerView.tsx
 - frontend/components/ask/Composer.tsx
 - frontend/components/source/SourceViewer.tsx
 - frontend/lib/useJobs.ts
 - frontend/lib/errorKinds.ts
 - frontend/lib/useAsk.ts
 - frontend/lib/api.ts
 - frontend/lib/sse.ts
 - frontend/lib/types.ts
 - frontend/e2e/smoke.spec.ts
 - frontend/e2e/fake-backend.ts
 - frontend/e2e/fixtures.ts
tests:
 - tests/test_llm_usage.py (T030)
 - tests/test_llm.py (T031)
 - tests/api/test_papers_jobs.py (T040)
 - tests/api/test_usage_errors.py (T046)
 - frontend/tests/library.test.tsx (T057)
 - frontend/tests/states.test.tsx (T063)
 - frontend/tests/usage-meter.test.tsx (T065)
 - frontend/e2e/smoke.spec.ts "US3 library", "US5 states: ..." (T059, T066)
 - scripts/checkpoint_6_web.py library states (0 model requests)
---

## Prompt

/sp.implement the US3 (library: upload with progress, duplicates, delete, re-process) and US5 (designed failure states, request counter, long-wait rule) tasks in every layer. Tests first, one commit per task. Run checkpoint 6's library and states parts (0 model requests) and show their output, then stop.

## Response snapshot

Implemented T032–T033, T040–T042, T046–T048, T057–T059 and T063–T066, one commit per task, with each test task committed failing first (T030/T031 were already committed red).
- **Engine:** a shared SQLite daily counter, a provider refresh from OpenRouter's /key endpoint and the daily pre-check.
- **Long-wait rule:** a requested wait over 60 s raises RateLimitedError, and X-RateLimit-Reset is trusted only within 48 h, with the raw header logged.
- **Errors:** every terminal LLMError carries a reason.
- **Fix to T032:** the usage database is now prepared once per process, because the WAL switch could fail with "locked" when two processes started at once.
- **API:** a FIFO ingest job worker with chunked 25 MB uploads, the %PDF- check, temp cleanup and SSE fan-out. Also the papers, jobs, reprocess and delete routes; /api/usage with a 30 s throttle; /api/search; and `attempts` on model_busy.
- **Frontend:**
  - A Library screen with drop/chooser uploads, phase rows, attach and duplicate copy, cards, confirmed delete and re-process.
  - useJobs streams job events, polling when the stream fails.
  - Designed states for every failure kind, with all copy in errorKinds, and a usage meter in the header.
  - Playwright tests for US3 and US5.

Checkpoint 6 `library states`: every check passed, with 0 LLM requests (0 planned, 0 retries). The provider's own count stayed at 35/50.

## Outcome

- ✅ Impact: US3 and US5 are complete in the engine, API, frontend and checkpoint.
- 🧪 Tests: pytest 549 passed; Vitest 131 passed; Playwright 16 passed (US1–US3, US5 × desktop/phone); checkpoint 6 library+states PASS, 0 model requests.
- 📁 Files: see the list above.
- 🔁 Next prompts: US4 (T043–T045, T060–T062), then polish (T067–T071).
- 🧠 Reflection:
  - An endless SSE endpoint can't be tested through TestClient (it buffers the whole body), so the registry's close_streams() ends the streams. Shutdown and the tests share it.
  - page.route can't stream bodies over time, so the busy countdown e2e uses an in-page fetch wrapper.

## Evaluation notes (flywheel)

- Failure modes observed:
  - A flaky "database is locked" from PRAGMA journal_mode under concurrent processes, fixed.
  - A Bash heredoc parse failure, worked around with patch scripts.
- Graders run and results (PASS/FAIL): pytest PASS; vitest PASS; playwright PASS; checkpoint 6 library states PASS.
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): wire NotFound's "Search all papers" to scope selection once US4 lands.
