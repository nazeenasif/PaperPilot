# Implementation Plan: Paper Summaries and Cross-Paper Comparison

**Branch**: `004-summaries-comparison` | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/004-summaries-comparison/spec.md`

## Summary

Add structured, cited **summaries** of one paper (TL;DR + Problem, Method, Data, Results,
Limitations) and **comparison tables** of 2–4 papers, built from the same grounding pipeline as
answers: retrieval with `library.search`, numbered `<passage>` prompts, `llm.generate` (the only
LLM boundary, with retries, the shared request counter and the long-wait rule) and
`review_reply` citation checks — generalised to an explicit set of allowed passage numbers so
each part is validated on its own (research R1). The TL;DR is generated from the verified
sections and checked in code: every sentence cites, its citations are a subset of the verified
sections' citations, and every number it states appears in the sections it traces to (R3).
Comparison rows are one request per aspect, retrieved per paper, returned as JSON cells and
parsed tolerantly; a malformed row is a failed row with a retry (R4). Results are saved in a
SQLite cache keyed by paper IDs, passage fingerprints, aspects, prompt version and `LLM_MODEL`,
and removed on delete or re-process (R6). Every run has a plan known before it starts and is
refused when today's remaining requests are fewer (R8). The web app gains Summarize and Compare
tabs that stream per-part progress and show each part only after its check. Checkpoint 7 runs
the LoRA summary and the BERT–RAG comparison (plan 10 requests) and lists every claim for the
hand check (R11).

## Technical Context

**Language/Version**: Python 3.12 (engine, API); TypeScript 6 strict (frontend)
**Primary Dependencies**: existing only — FastAPI 0.143 (built-in SSE), openai SDK (inside
`llm.py`), ChromaDB, sentence-transformers; Next 16.4.1, React 19.3, Tailwind 4, shadcn/ui,
motion, react-pdf. **No new dependencies** (`sqlite3`, `json`, `hashlib` are standard library).
**Storage**: ChromaDB (unchanged); `<LIBRARY_DIR>/results.sqlite3` (new, saved summaries and
comparisons); `<LIBRARY_DIR>/usage.sqlite3` (unchanged)
**Testing**: pytest with the scripted LLM and fake embedder (`tests/conftest.py`); Vitest +
Testing Library; Playwright with the fake backend; `scripts/checkpoint_7_summaries.py` (real)
**Target Platform**: Windows dev machine; localhost only (127.0.0.1)
**Project Type**: web application (engine package + thin API + Next.js frontend), as Feature 3
**Performance Goals**: reopening a saved result < 1 s with 0 requests (SC-003); a summary
completes in ~6 model calls (≈ 30–90 s on the free model), with progress per part
**Constraints**: ≤ 6 requests per summary, ≤ 1 per aspect per comparison; every call inside
its `llm.OUTPUT_TOKENS` limit including reasoning (answers 2048, summary and comparison calls 4096, R5); ~50 free requests/day; one model task at a
time; no unchecked text ever streamed
**Scale/Scope**: a library of ~5–20 papers; 5 facets; 2–4 papers × ≤ 5 aspects per comparison

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle (v1.3.0) | Check | Status |
|---|---|---|
| I. Plain, typed code | Plain Python with type hints and docstrings, no orchestration framework; frontend strict TypeScript, no LLM SDK | ✅ |
| II. Modular package, single LLM boundary | No new module (R7): prompts/parsing/TL;DR check in `prompts`, orchestration in `service`, results cache in `library`; only `llm.py` calls the model; `api/` maps requests and errors only | ✅ |
| III. OpenAI-compatible LLM, free by default | Unchanged; no provider-specific JSON mode (R4) | ✅ |
| IV. Local embeddings, persistent store | Retrieval only; no re-embedding; store schema unchanged | ✅ |
| V. Grounded answers (NON-NEGOTIABLE) | Every part validated by the same `review_reply` against its own passages; invalid → held back, none → not reported; TL;DR checked for subset citations, cited sentences and traceable numbers; nothing unchecked streamed or shown as verified | ✅ |
| VI. Secrets and data hygiene | Results DB under gitignored `data/`; checkpoint 6 `secrets` part covers the new endpoints' responses | ✅ |
| VII. Testable checkpoints, measured quality | Pure logic (prompt builders, `parse_row`, `check_tldr`, `check_citations(allowed)`) unit-tested offline; checkpoint 7 with request plan and hand-verified claims; the eval harness stays deferred (spec Out of Scope) | ⚠ justified below |
| VIII. Simplicity, small commits | Reuses the answer pipeline; no new dependency; SQLite like usage accounting; no new module | ✅ |
| IX. Visible grounding in a web interface | Every citation in sections, TL;DR and cells opens the PDF with the highlight; progress per part; designed states per part and per run | ✅ |

**Post-design re-check (after Phase 1)**: unchanged. The contracts add functions to `service`,
`prompts` and `library`, a parameter to `check_citations`/`review_reply`, one error class, and
one error kind rename (`busy_question` → `busy_task`, both halves in one commit).

## Project Structure

### Documentation (this feature)

```text
specs/004-summaries-comparison/
├── spec.md
├── plan.md              # this file
├── research.md          # R1–R11
├── data-model.md        # Part, Summary, Comparison, SavedResult, RequestPlan
├── quickstart.md
├── contracts/
│   ├── engine-api.md
│   └── web-api.md
├── checklists/requirements.md
└── tasks.md             # /sp.tasks
```

### Source Code (repository root)

```text
paperpilot/
├── prompts.py        # + facets/aspects, NOT_REPORTED, SUMMARY_PROMPT_VERSION, format_passages,
│                     #   build_section/tldr/row_prompt, parse_row, check_tldr,
│                     #   check_citations(allowed=)
├── service.py        # + summarize, compare, saved_*, *_plan, number_passages; review_reply(allowed=)
├── library.py        # + results cache (save/load/forget_results, passage_fingerprint);
│                     #   delete/reprocess forget results
└── errors.py         # + RowFormatError

api/
├── routes.py         # + /api/summaries*, /api/comparisons*; busy_task
├── schemas.py        # + SummarizeIn, CompareIn, summary_body, comparison_body
├── errors.py         # + not_saved, busy_task, daily_limit.needed
└── state.py          # question_lock → model_lock

frontend/
├── app/summarize/page.tsx               # paper picker + saved summaries
├── app/summarize/[paperId]/page.tsx     # one summary
├── app/compare/page.tsx                 # form + table
├── components/summary/                  # SummaryView, TldrCard, SectionCard, PartState, CostButton
├── components/compare/                  # CompareForm, CompareTable, CompareCell
├── components/app/Header.tsx            # four tabs
├── components/library/PaperCard.tsx     # Summarize button
└── lib/                                 # useSummary.ts, useComparison.ts, types.ts, errorKinds.ts (copy)

tests/
├── test_prompts_summary.py   # builders, parse_row, check_tldr, check_citations(allowed)
├── test_summarize.py         # scripted runs: states, plan, stop rules, saving, retry
├── test_compare.py
├── test_results_cache.py     # keys, staleness, invalidation, concurrency
└── api/test_summaries_api.py, api/test_comparisons_api.py

scripts/checkpoint_7_summaries.py
docs/verification/checkpoint-7-<date>.md   # generated, then filled by hand
```

**Structure Decision**: the Feature 3 layout (engine package, thin `api/`, `frontend/`); all
grounding stays in the package.

## Key Decisions (rationale in research.md)

1. **One grounding pipeline** (R1): `check_citations`/`review_reply` take an `allowed` set;
   `format_passages` is shared by answer, section and row prompts; `ask()` behaviour unchanged
   (its tests unchanged).
2. **Query-focused facets** (R2): 4 passages per facet from one paper; below threshold → not
   reported with no request.
3. **TL;DR check in code** (R3): generated from verified sections only; four rules (not found,
   every sentence cites, citations ⊆ sections' citations, numbers appear in traced sections);
   failure holds back the TL;DR only.
4. **Comparison rows as JSON** (R4): one request per aspect; per-paper retrieval (3 each); one
   object per cell; tolerant parser; malformed → failed row with retry.
5. **Output budget** (R5, amended): `max_tokens` per task kind (answers 2048, summary and
   comparison calls 4096), because reasoning dominates; cut-off is a per-part failure.
6. **SQLite results cache** (R6): key = paper IDs + passage fingerprints + aspects + prompt
   version + model; explicit forget on delete/re-process; stale results readable, never current.
7. **No new module** (R7).
8. **Run control** (R8): plan before start, pre-check against remaining requests, stop on
   systemic failures, one shared model lock (`busy_task`).
9. **Map-reduce rejected** (R10).

## Interfaces

See `contracts/engine-api.md` and `contracts/web-api.md`. Idempotency: `GET` endpoints never
send a model request; `POST` without `regenerate` returns the current saved result with 0
requests. Errors before a stream are plain JSON (`invalid_request`, `unknown_paper`,
`busy_task`, `daily_limit` with `needed`); failures inside a run are part states, so a stream
always ends with the (partial) result unless an unexpected error occurs (`internal`).

## Phase plan (for /sp.tasks)

1. **Engine foundations**: `check_citations(allowed)`, `review_reply(allowed)`,
   `format_passages`, `number_passages` (tests first; `ask` tests must stay unchanged).
2. **US1 + US4 (summaries, per-part states)**: facets, section and TL;DR prompts, `check_tldr`,
   `summarize`, plan and stop rules; API stream; Summary screen.
3. **US2 (saved results)**: results cache, keys, staleness, invalidation hooks, reopen and
   regenerate, part retry; API GET; picker and "Saved … · reopening cost 0 requests".
4. **US3 (comparison)**: aspects, row prompt, `parse_row`, `compare`; API; Compare screen.
5. **US5 (cost and limits)**: plan in every response, pre-check, `model_lock`/`busy_task`,
   per-part busy/long-wait/daily-limit states; cost on every button.
6. **Polish**: phone width and keyboard e2e, checkpoint 6 `secrets` covers new endpoints,
   known-limitations section, checkpoint 7 and the hand-verification record.

## Risks

- **Free-model JSON reliability**: rows may come back malformed. Mitigation: tolerant parser,
  per-row retry (1 request), malformed-rate printed by checkpoint 7; JSON mode can be added in
  `llm.py` later without contract changes.
- **The TL;DR number check may reject a correct paraphrase** (e.g. "10k" for "10,000").
  Mitigation: normalisation of separators and `k`/`×` forms; the rejected text stays viewable;
  rejections are counted in checkpoint 7.
- **Request budget**: a full checkpoint uses 10 requests (20 with retries). Mitigation: plan
  printed and checked against `usage.py` before any request; `states` part is offline.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| No eval-harness run although new prompts are introduced (Principle VII) | The spec puts the harness out of scope (as Feature 2 did); summary quality is measured instead by checkpoint 7's citation checks and ≥ 10 hand-verified claims with fault attribution | Building the harness here would double the feature; the hand check records the baseline it will use |

## ADRs

- [ADR-0008: Per-Part Grounding and Structured Output](../../history/adr/0008-per-part-grounding-and-structured-output.md)
  — one validator scoped by allowed passage numbers, part states, the TL;DR check in code, JSON
  comparison rows with a tolerant parser, per-part output budget (research R1, R3–R5).
- [ADR-0009: Saved Results and Multi-Request Runs](../../history/adr/0009-saved-results-and-multi-request-runs.md)
  — SQLite results cache with fingerprinted keys and explicit invalidation, request plan and
  pre-check, stop rules, one shared model lock (research R6, R8, R10).

Not ADR-worthy: facet queries and sizes (R2, tunable constants), module placement (R7, follows
the constitution).
