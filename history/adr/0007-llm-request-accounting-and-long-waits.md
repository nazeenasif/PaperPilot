# ADR-0007: LLM Request Accounting and Long Waits

> **Scope**: Document decision clusters, not individual technology choices. Group related decisions that work together (e.g., "Frontend Stack" not separate ADRs for framework, styling, deployment).

- **Status:** Accepted (amends ADR-0003's retry policy)
- **Date:** 2026-10-24
- **Feature:** 003-web-app
- **Context:**
  - **What the web app needs:** the app shows "Requests today N / 50" (FR-024).
    - The count must include every request the engine makes from any caller, the app or a
      script, retries included.
    - It must survive restarts and must not lose counts when callers run at the same time
      (FR-025).
    - The engine must not spend a request once the daily limit is reached (FR-026, SC-007).
  - **Long waits under ADR-0003:** a hinted wait was capped at 60 s and then retried, up to 4
    attempts.
    - After a daily-limit 429 that pointed hours ahead, this spent three more requests and about
      3 minutes of countdown on calls that couldn't succeed.
    - FR-023a–c ask the engine to stop at once instead, and to trust `X-RateLimit-Reset` only
      within 48 hours.
  - **Provider facts verified during planning** (OpenRouter documentation and the key endpoint,
    2026-10-24):
    - The free daily limit is counted per UTC day.
    - The `X-RateLimit-*` headers appear **only on 429 errors**, with undocumented units.
    - `GET /api/v1/key` returns `free_model_daily_requests {used, limit, remaining}` and isn't
      a model request. It read `34 / 50`, matching the project's own estimate of about 33.
  - **Module constraint:** Principle II allows only `llm.py` to talk to the provider, and allows
    no new package modules without an amendment.

## Decision

- **Where:** all request accounting lives in `paperpilot/llm.py`, next to the retry loop. No new
  module is added.
- **Shared counter:** a SQLite database at `<LIBRARY_DIR>/usage.sqlite3`.
  - **Schema:** one row per UTC day, holding `used`, `request_limit`, `source` (`local` or
    `provider`) and `updated_at`.
  - **Increments:** every attempt, first or retry, increments `used` inside `BEGIN IMMEDIATE`,
    with WAL mode and a 5 s busy timeout. This is safe across threads and across processes (the
    app and a script).
  - **Day change:** a new UTC day is a new row, so the counter resets at 00:00 UTC.
  - **Alongside:** the per-process `request_counts()` for checkpoint budgets (Feature 2) is
    kept.
- **Provider figure preferred:**
  - `refresh_usage()` reads `free_model_daily_requests` when `LLM_PROVIDER=openrouter` and
    overwrites the day's `used` and `limit` with source `provider`.
  - It runs at API start, after each question, after each 429, and on `GET /api/usage` at most
    once every 30 s.
  - A 429 whose headers describe the daily limit also updates the row.
  - On failure, or with another provider, the local count stands.
  - `DAILY_REQUEST_LIMIT` (default 50) applies until the provider reports its own limit.
- **Pre-check:** before any request, `generate()` raises `DailyLimitError(used, limit,
  resets_at)` when `used >= limit`. No request is sent, from the app or from a script.
- **Long waits:**
  - When a hinted wait (`Retry-After` or `X-RateLimit-Reset`) is longer than 60 s, `generate()`
    stops at once and raises `RateLimitedError(until, daily)` ("rate limited until <time>").
    Exactly one request has been spent.
  - `daily` is true when the 429's `X-RateLimit-Limit` matches the daily limit, or when a
    refreshed key reading shows `remaining == 0`. The UI then shows the daily-limit screen,
    otherwise "try again at <local time>".
  - Waits of 60 s or less keep ADR-0003's behaviour: wait, retry, up to 4 attempts.
- **Reset header sanity:** `X-RateLimit-Reset` is read as epoch milliseconds. It is trusted only
  if it resolves to a time in the future and within 48 hours; otherwise it is ignored and the
  2/4/8 s backoff applies.
  - A value actually given in seconds would resolve to 1970 and be ignored safely.
  - The raw header value is included in the WARNING retry log line, so its units can be confirmed
    from the first real 429 and recorded in research.
- **Progress hook:** `generate(..., on_retry=…)` reports attempt, maximum attempts, wait and
  reason before each retry wait, for the countdown (ADR-0005).
- **Tests:** offline, with the fake client.
  - Long `Retry-After`, a wait of exactly 60 s, a reset in the past, a reset beyond 48 h, and a
    reset in seconds.
  - Daily versus per-minute classification, and the pre-check.
  - Concurrent increments from threads and from two processes.
  - A provider refresh that succeeds and one that fails.

## Consequences

### Positive

- The usage meter is authoritative whenever OpenRouter is the provider. It also covers requests
  made outside PaperPilot with the same key, which a local count can't see.
- No request is wasted at the daily limit or on a wait that can't clear soon. A long wait now
  costs exactly one request (SC-013) instead of four.
- Scripts and the app share one number and one guard, so a morning checkpoint run is reflected
  in the app's meter.
- The behaviour stays inside the single LLM boundary and is fully unit-tested without network
  access.
- A wrong unit in `X-RateLimit-Reset` can't cause a hours-long sleep or a busy loop.

### Negative

- `llm.py` grows a persistence concern: SQLite, a schema and concurrency. It is no longer purely
  "send a request and retry".
- The key endpoint is OpenRouter-specific. Other providers fall back to the local count, which
  can't see outside usage.
- One extra HTTPS call after each question, cheap and not counted against the limit.
- The local count can briefly drift from the provider's between refreshes, for example when two
  callers race just before the limit. The provider's own 429 is the final safeguard (FR-027).
- Questions that would have succeeded after a wait of several minutes now stop and ask the
  researcher to try again later.
- The reset header's units are still unconfirmed until the first real 429.

## Alternatives Considered

- **Alternative A: rate-limit headers as the usage source** (the planning prompt's first idea).
  Impossible, because successful responses carry no `X-RateLimit-*` headers. Headers are used
  only on 429s.
- **Alternative B: local count only.**
  - Simpler, with no provider-specific call.
  - But blind to requests made elsewhere with the same key, so the meter could claim 20 / 50
    when the provider has seen 50.
- **Alternative C: a separate `usage` module.**
  - Cleaner separation.
  - But it needs a constitution amendment (Principle II's module list) for one table. The key
    endpoint call would also have to live in `llm.py` anyway, since that is the only module
    allowed to talk to the provider.
- **Alternative D: a JSON or text file counter.** No safe concurrent increments across
  processes without extra locking code.
- **Alternative E: keep ADR-0003's cap-and-retry for long waits.** Wastes three requests and
  minutes per daily-limit hit, and shows a countdown that can't succeed.
- **Alternative F: ask the researcher whether to wait** (clarification Q3, option C). More
  control, but an extra interaction for a case that almost always means "come back later".

## References

- Feature Spec: specs/003-web-app/spec.md (FR-023–FR-027, SC-006, SC-007, SC-013;
  clarifications Q2–Q3 and the researcher's refinements)
- Implementation Plan: specs/003-web-app/plan.md (Key Decisions 7–8)
- Data Model: specs/003-web-app/data-model.md (usage database)
- Related ADRs: ADR-0003 (LLM Boundary and Retry Policy; amended by this ADR), ADR-0005 (Web
  Stack and Progress Transport)
- Evaluator Evidence: specs/003-web-app/research.md R7–R8 (OpenRouter limits documentation;
  key endpoint reading 34/50 on 2026-10-24);
  history/prompts/003-web-app/4-localhost-binding-and-rate-limit-rules.spec.prompt.md
