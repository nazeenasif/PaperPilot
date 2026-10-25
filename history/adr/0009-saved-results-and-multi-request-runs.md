# ADR-0009: Saved Results and Multi-Request Runs

> **Scope**: Document decision clusters, not individual technology choices. Group related decisions that work together (e.g., "Frontend Stack" not separate ADRs for framework, styling, deployment).

- **Status:** Accepted (extends ADR-0007 from single questions to runs)
- **Date:** 2026-10-25
- **Feature:** 004-summaries-comparison
- **Context:**
  - **The free tier:** the configured free model allows about 50 requests per UTC day
    (ADR-0007).
    - A summary costs up to 6 requests and a comparison up to 5.
    - Regenerating on every view would exhaust the day in a few clicks, so reopening must cost
      0 requests and survive restarts (FR-016, SC-003).
  - **When a saved result stops being current:** its paper is re-processed or deleted, the
    configured model changes, or PaperPilot's instructions change (FR-017).
    - Paper IDs are the hash of the PDF bytes, so **re-processing the same PDF keeps the same
      ID**: a key built from paper IDs alone would not notice re-chunking.
  - **Runs of several requests:**
    - The cost must be shown and checked before the first request (FR-021–FR-023).
    - Finished parts must survive a later failure (FR-020).
    - A daily limit or long wait must stop the run with no further requests (FR-024).
  - **Feature 3's guard is too narrow:** it allows one question at a time, which would let a
    question and a summary compete for the same budget (FR-025).
  - **Constraints:** Principle II (no new module; `library` owns per-paper data); results must be
    shared by the API and scripts (checkpoint 7) and must not lose writes when both run.

## Decision

- **Store**: `<LIBRARY_DIR>/results.sqlite3`, one table `results(kind, key, paper_ids, result
  JSON, model, prompt_version, created_at)`.
  - WAL with `BEGIN IMMEDIATE` writes, set up once per process, as `usage.sqlite3` (ADR-0007).
  - Owned by `library` (`save_result`, `load_result`, `forget_results`,
    `passage_fingerprint`).
- **Key**: SHA-256 of `kind`, the sorted paper content IDs, each paper's **passage fingerprint**
  (hash of its stored passage ids and texts), the sorted aspects, `SUMMARY_PROMPT_VERSION`, and
  `LLM_MODEL`.
- **Invalidation, two ways**:
  1. **Explicit:** `delete_paper` and `reprocess_paper` call `forget_results(paper_id)`.
  2. **On lookup:** a row saved under another model, version or fingerprint is returned as
     **stale** with its reason. It is readable but never presented as current, and nothing is
     regenerated automatically.
- **Reuse**: GET endpoints and `summarize`/`compare` without `regenerate` return the current saved
  result with **0 requests**.
  - **Regeneration** writes a new result and replaces the old one only on completion.
  - **Part retries** re-run only `failed`/`not_started` parts (plus the TL;DR when a section
    changed) and rewrite the row.
- **Request plan before every run**:
  - A summary's plan is 6.
  - A comparison's plan is its number of aspects.
  - A retry's plan is its failed parts (+1 for the TL;DR).
  - The plan is returned with every saved result and shown on every button ("uses 6 requests ·
    41 left today").
- **Pre-check**: the engine raises `DailyLimitError` before any request when
  `llm.usage().remaining < plan`; the API returns `429 daily_limit` with `needed`.
- **Stop rules**:
  - `cut_off`, `empty` and `malformed` fail one part, and the run continues.
  - Daily limit, long wait (`RateLimitedError`), `model_busy` after all retries, and
    `model_unavailable` **stop** the run:
    - finished parts are kept and saved;
    - the rest are `not_started` with the reason;
    - no further request is sent.
  - Each part makes at most one `llm.generate` call, so first attempts never exceed the plan;
    retries are reported separately.
- **One model task at a time**: Feature 3's question lock becomes `model_lock`, shared by
  questions, summaries and comparisons. A refused start returns `409 busy_task`, which replaces
  `busy_question` in API and frontend in one commit.

## Consequences

### Positive

- **Free reopening:** saved summaries and comparisons reopen instantly with 0 requests, after
  restarts too, and from both the app and the scripts.
- **Exact staleness:** explicit hooks catch re-processing and deletion; the key catches what
  hooks cannot (a model change in `.env`, a prompt-version bump). Users see why a result is old.
- **No surprise costs:**
  - The cost is known before any request.
  - A run that can't finish within today's budget never starts.
  - A provider-side limit or overloaded model stops the run instead of burning up to 4 attempts
    per remaining part.
- **Partial progress kept:** finished parts are never lost; a failed part costs 1 request to
  retry, not a whole new run.

### Negative

- **Another file:** a second SQLite file and its upkeep (one more file under `data/`; stale rows
  linger until replaced or their paper is deleted).
- **Bounded staleness:** the saved result can lag the library in one case, a library change made
  outside the engine (for example, editing ChromaDB by hand) without a model change. This is
  caught only by the fingerprint check on lookup.
- **Conservative refusals:** the pre-check uses the plan's maximum, so a run that would have used
  fewer requests (facets below the threshold) can be refused when only a few requests remain.
- **Stopping can strand parts:** stopping on `model_busy` means one overloaded moment leaves
  parts `not_started` that might have succeeded seconds later; the researcher has to retry them.
- **Contract change:** the `busy_question` → `busy_task` rename touches Feature 3's API contract
  and frontend copy.

## Alternatives Considered

- **Storage:**
  - **JSON files per result:** no atomic replace across the API and scripts without extra
    locking. Rejected.
  - **Storing results in ChromaDB metadata:** the wrong tool, coupling saved text to the vector
    store and to re-embedding. Rejected.
  - **An in-memory cache in the API:** lost on restart and invisible to scripts. Rejected.
- **Keys:**
  - **Paper IDs only:** misses re-chunking, model and instruction changes. Rejected.
  - **No explicit invalidation (key only):** works, but leaves dead rows for deleted papers and
    makes "why is this old?" unanswerable. Rejected.
- **Run control:**
  - **Start regardless and stop at the limit:** wastes requests on runs that can't finish.
    Rejected.
  - **Exact pre-computed plan** (retrieve first, count facets above the threshold): a precise
    cost, but every cost display would need a retrieval pass. Kept as a possible refinement;
    the maximum is simpler and safe.
  - **Continue past `model_busy`:** may spend up to 4 attempts × remaining parts during an
    outage. Rejected.
  - **Separate locks per task type:** a question and a summary would race for the same daily
    budget and the same free-model rate limit. Rejected.
  - **Map-reduce summaries:** ~60 requests per paper (FR-006, research R10). Rejected.

## References

- Feature Spec: [specs/004-summaries-comparison/spec.md](../../specs/004-summaries-comparison/spec.md)
- Implementation Plan: [specs/004-summaries-comparison/plan.md](../../specs/004-summaries-comparison/plan.md)
- Research: R6 (cache), R8 (run control), R10 (map-reduce), R11 (checkpoint 7 plan) in
  [research.md](../../specs/004-summaries-comparison/research.md); SavedResult and RequestPlan in
  [data-model.md](../../specs/004-summaries-comparison/data-model.md); error kinds in
  [contracts/web-api.md](../../specs/004-summaries-comparison/contracts/web-api.md)
- Related ADRs: ADR-0003 (retry policy), ADR-0005 (web stack and progress transport), ADR-0007
  (request accounting and long waits)
- Evaluator Evidence: checkpoint 7 request totals and reopen check (to be recorded)
