---

description: "Task list for Feature 4: Paper Summaries and Cross-Paper Comparison"
---

# Tasks: Paper Summaries and Cross-Paper Comparison

**Input**: Design documents from `/specs/004-summaries-comparison/`
**Prerequisites**: plan.md, spec.md, research.md (R1–R11), data-model.md,
contracts/engine-api.md, contracts/web-api.md, quickstart.md; ADR-0008, ADR-0009

**Order (as requested)**: engine first, then the API, then the frontend. Within each layer,
tasks follow user-story priority: US1 (P1, summary), US2 (P1, saved results), US4 (P1, per-part
states), US3 (P2, comparison), US5 (P2, cost and limits). A story is complete when its frontend
section's check passes; the engine and API sections also end in runnable checks.

**Tests first**: every implementation task is preceded by a test task that must fail first.
When a test passes at once because the behaviour already exists, the commit says so and a
mutation run (break the code briefly, see the test fail, restore) shows the test bites.
Commit after each task: one commit per task, with a message naming the files it touches.

**Model safety**: unit, API and component tests use the scripted fake LLM only
(`tests/conftest.py` `ScriptedLLM`, `fake_answers`; real clients and the key endpoint are
blocked by the autouse guards). Frontend tests mock `fetch`; Playwright uses the fake backend.
Only `scripts/checkpoint_7_summaries.py` (real parts) and `scripts/usage.py` reach OpenRouter.
Checkpoint 7 **plans 10 requests with a cap of 20** (2 × plan, the Feature 2 budget rule) and
prints planned requests, retries and totals per part and in all.

**`ask()` stays as it is**: the existing tests for `ask()` and its prompts
(`tests/test_service.py`, `tests/test_prompts.py`, `tests/api/test_ask.py` except the
`busy_task` rename in T029) MUST pass **unchanged** after the shared citation check is
generalised (T004).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 from spec.md; no label for Setup, Foundational and Polish

## Path Conventions

- Engine: `paperpilot/`; API adapter: `api/`; Python tests: `tests/` and `tests/api/`
- Frontend: `frontend/` (`app/`, `components/`, `lib/`, `tests/`, `e2e/`)
- Scripts: `scripts/`; verification records: `docs/verification/`

---

## Phase 1: Setup

- [X] T001 [P] Add summary fixtures to `tests/conftest.py`:
  - `summary_paper(make_pdf)`: a generated paper whose sections match the five facets (Abstract with the problem; Method; Experiments naming two datasets; Results with numbers such as "10,000 times" and "3 times"; Limitations), long enough for ≥ 4 passages per facet with the default chunking.
  - `second_paper`: a different generated paper with no limitations section, for comparisons and not-reported cells.
  - `row_reply(cells: dict[str, str]) -> str` in `tests/fake_llm.py`: a JSON row reply (`{"cells": [{"paper": "P1", "text": …}]}`), plus `fenced(text)` wrapping it in a ```json fence.
  - No behaviour changes; the full `pytest` still passes.
- [X] T002 [P] Add the Feature 4 types to `frontend/lib/types.ts` (Part, PartState, Summary, Comparison, ComparisonRow, RequestPlan, SummaryListItem, the `busy_task` and `not_saved` kinds) exactly as `data-model.md` and `contracts/web-api.md` name the fields; `npm --prefix frontend run typecheck` passes.

---

## Phase 2: Foundational (blocks every story)

### One grounding pipeline (research R1, ADR-0008)

- [X] T003 Create failing tests in `tests/test_grounding_parts.py`:
  - `check_citations(text, allowed={5, 6, 7})`: 5–7 valid, 1 and 8 invalid, uncited sentences listed; `check_citations(text, passage_count=4)` equals `allowed={1, 2, 3, 4}`.
  - `review_reply(text, allowed=…)`: invalid → `NOT_FOUND` with `rejected_answer` and the warning naming the numbers; none → `no_citations`; not-found sentence → `model_not_found`; `review_reply(text, passage_count=n)` unchanged.
  - `format_passages(passages)` returns exactly the passage block `build_answer_prompt` produces today (escaped, reference markers stripped).
  - `number_passages(results, seen)`: numbers continue across calls; a passage id seen before keeps its first number.
- [X] T004 Generalise in place in `paperpilot/prompts.py` and `paperpilot/service.py`, so T003 passes and `ask()` is unchanged:
  - `paperpilot/prompts.py`: `check_citations(text, passage_count=None, allowed=None)`; factor `format_passages` out of `build_answer_prompt`.
  - `paperpilot/service.py`: `review_reply(text, passage_count=None, allowed=None)`; `_number` becomes `number_passages(results, seen=None)`.
  - Check: `git diff --stat tests/test_service.py tests/test_prompts.py tests/api/test_ask.py` is empty, and the full `pytest` passes.

**Checkpoint (foundation)**: full `pytest` passes with the `ask()` tests untouched.

---

## Phase 3: Engine (by story priority)

### US1 (P1): a summary with cited sections

- [X] T005 [P] [US1] Create failing tests in `tests/test_prompts_summary.py`:
  - **Constants:** `FACETS` has problem, method, data, results, limitations in that order, each with a retrieval query and label; `NOT_REPORTED == "Not reported in the retrieved passages."`; `SUMMARY_PROMPT_VERSION` is an int.
  - **Builders:** `build_section_prompt(facet, passages)` contains the facet instruction (≤ 80 words, cite every sentence, copy numbers exactly, reply `NOT_REPORTED` when unsupported) and `format_passages(passages)` with their run-wide numbers; `build_tldr_prompt(sections)` lists only the given verified sections with their citation numbers and asks for ≤ 60 words, ≤ 3 sentences.
  - **`check_tldr`** (research R3), with verified sections Problem `[1]` and Results `[4]` ("about 10,000 times", "3 times"):
    - every sentence cites `[1]` or `[4]` and its numbers appear in its sources → ok, `sources` per sentence (e.g. `["Results"]`);
    - an uncited sentence → fails, problem names the sentence;
    - a citation to `[9]` (no verified section cites it), or to a passage cited only by a held-back section → fails;
    - "10,000" written as "10k" or "10 000" is accepted; "20,000" is rejected ("states 20,000, which its sources do not contain");
    - the not-found sentence → `not_found`; an empty sections list → not reported without building a prompt.
  - **Known gap (documented, not fixed):** a non-numeric sentence with a valid citation whose sources do not say it passes; the test asserts `ok` and carries a comment pointing to `docs/known-limitations.md` (the F1 pattern).
- [X] T006 [US1] Implement in `paperpilot/prompts.py`: `Facet`, `FACETS`, `NOT_REPORTED`, `SUMMARY_PROMPT_VERSION = 1`, `SECTION_INSTRUCTION`, `TLDR_INSTRUCTION`, `build_section_prompt`, `build_tldr_prompt`, `VerifiedSection`, `TldrCheck` and `check_tldr` (four rules, number normalisation for `,`, thin spaces, `.`, `%`, `×`/`x`, `k`), so T005 passes.
- [X] T007 [US1] Create failing tests in `tests/test_summarize.py` (fake embedder, `summary_paper`, `fake_answers`):
  - Five facets are retrieved with `library.search(query, k=4, paper_ids=[paper_id])` (spy), in order; every passage belongs to the paper.
  - Passages are numbered once per summary; a passage shared by two facets keeps one number.
  - Each section reply is validated only against its own facet's numbers (a section citing another facet's passage is held back).
  - The TL;DR prompt contains only verified sections; its reply passes `check_tldr`.
  - The result has `tldr` and five sections in order, `passages`, `requests` (`planned == 6`, `retries == 0`), tokens per part, `model`, `prompt_version`, `created_at`.
  - Events: `plan` first; per part `progress` (searching → reading → generating → checking) then `part`; no event before a part's `part` event contains its text.
  - `UnknownPaperError` for an unknown paper, with 0 requests.
- [X] T008 [US1] Implement `summarize()` in `paperpilot/service.py` (no saving yet): per facet retrieve, gate on the relevance threshold, one `llm.generate` call, `review_reply(allowed=…)`; then the TL;DR from verified sections and `check_tldr`; part events through `on_event`; `Summary` and `Part` dataclasses as `data-model.md`. T007 passes.

### US2 (P1): saved results, reopen at no cost, regenerate

- [X] T009 [P] [US2] Create failing tests in `tests/test_results_cache.py`:
  - `save_result`/`load_result` round-trip a summary under `<LIBRARY_DIR>/results.sqlite3`; the key is order-insensitive for paper IDs and aspects.
  - Staleness: changing `LLM_MODEL` → `model_changed`; bumping `SUMMARY_PROMPT_VERSION` (monkeypatch) → `instructions_changed`; re-chunking a paper (different `CHUNK_WORDS`, re-process) → `passages_changed`.
  - `delete_paper` and `reprocess_paper` remove every saved result that includes the paper (`forget_results` returns the count); results for other papers stay.
  - `passage_fingerprint` is stable across calls and changes when a passage text changes.
  - Two processes saving at once lose nothing (spawned processes, as `test_llm_usage.py`).
- [X] T010 [US2] Implement the results cache in `paperpilot/library.py` (`ResultKey`, `save_result`, `load_result`, `forget_results`, `passage_fingerprint`; WAL, `BEGIN IMMEDIATE`, set up once per process) and call `forget_results` from `delete_paper` and `reprocess_paper`, so T009 passes.
- [X] T011 [US2] Create failing tests in `tests/test_summarize_saved.py`:
  - After a summary, `summarize(paper_id)` again returns the saved summary with **0** new requests (`llm.request_counts()` unchanged, no `generate` call).
  - `saved_summary(paper_id)` returns it (`status: current`); after a model change it returns `stale` with the reason and `summarize(paper_id)` without `regenerate` does not regenerate it silently: it returns the stale result marked stale.
  - `regenerate=True` writes a new summary; if the regeneration raises midway (scripted `RuntimeError` in the third facet), the old saved summary is still returned unchanged.
  - `retry_parts=["method"]` with a saved summary whose Method failed (`cut_off`) calls `generate` exactly twice (Method + TL;DR) and keeps the other parts from the saved summary.
  - `summary_plan(paper_id)` is `{max_requests: 6}`; `summary_plan(paper_id, retry_parts=["method"])` is `{max_requests: 2}`.
- [X] T012 [US2] Implement saving, reuse, `regenerate`, `retry_parts`, `saved_summary` and `summary_plan` in `paperpilot/service.py`, so T011 passes.

### US4 (P1): "Not reported" and held-back parts, the rest stays visible

- [X] T013 [US4] Create failing tests in `tests/test_summarize_states.py` (scripted replies per facet):
  - A section reply with no citations → `not_reported` (`no_citations`); the not-found or `NOT_REPORTED` sentence → `not_reported` (`model_not_found`).
  - A facet whose best passage is below `RELEVANCE_THRESHOLD` → `not_reported` (`below_threshold`) with **no** `generate` call (the plan's maximum is 6; actual planned requests 5).
  - A section citing a passage outside its facet → `held_back` with `rejected_text`, `citations.invalid`, warning; other sections `verified`.
  - `LLMError(reason="cut_off")` and `reason="empty"` for one facet → that part `failed` with the reason; the run continues and the other parts are verified.
  - TL;DR failing `check_tldr` → `held_back` with the problems as warning; all five sections still in the result.
  - All five sections not verified → TL;DR `not_reported` (`no_verified_sections`) and no TL;DR request (total `generate` calls == 5).
  - No part ever carries text with `state != verified`; `rejected_text` only on `held_back`.
- [X] T014 [US4] Implement the per-part state rules in `paperpilot/service.py` (`_part_from_reply`, cut-off/empty as part failures, the no-verified-sections TL;DR rule), so T013 passes.

### US3 (P2): comparison table, one request per aspect, JSON cells

- [X] T015 [P] [US3] Create failing tests in `tests/test_prompts_compare.py`:
  - `ASPECTS` has problem, method, datasets, results, limitations with queries; cells are ≤ 50 words.
  - `build_row_prompt(aspect, papers)` labels papers `P1…Pn` with their titles, lists each paper's passages with run-wide numbers, asks for JSON only with the exact shape, and tells a paper with no passages to answer `NOT_REPORTED`.
  - `parse_row`: plain JSON; JSON in a ```json fence; JSON with a sentence before and after; returns `{label: text}`; extra cells and keys ignored; a missing label is absent from the result; a non-string `text` dropped.
  - Malformed replies (`""`, `"not json"`, `{"cells": "x"}`, truncated JSON, a JSON list) raise `RowFormatError`.
  - **Note (2026-11-04, research R2):** aspects use the shared `prompts.FACETS` table for their query, preferred sections and exclusions rather than their own copies, so Related Work and Front Matter are excluded from comparisons too. `datasets` is the `data` facet. Not yet settled: how a Limitations row splits its passages when `k=3` (T017), and whether a paper's cell is gated on a whole-paper search as summaries are; `facet_retrieval` is fixed at 4 passages today.
- [X] T016 [US3] Implement `ASPECTS`, `ROW_INSTRUCTION`, `build_row_prompt` and `parse_row` in `paperpilot/prompts.py`, and `RowFormatError` in `paperpilot/errors.py`, so T015 passes.
  - **Note (2026-11-05, research R3):** `ROW_INSTRUCTION` carries `prompts.SCOPE_RULE`, as the section and TL;DR instructions do; add a test.
- [X] T017 [US3] Create failing tests in `tests/test_compare.py` (`summary_paper`, `second_paper`, `fake_answers`, `row_reply`):
  - Input checks: 1 or 5 papers, duplicates, no aspects, an unknown aspect → `ValueError`; an unknown paper → `UnknownPaperError`; 0 requests in every case.
  - Per aspect and per paper: `library.search(aspect_query, k=3, paper_ids=[p])` (spy); passages de-duplicated and numbered once per comparison.
  - Cells are validated against their own paper's numbers in that row: citing the other paper's passage → that cell `held_back`; the other cell `verified`.
  - A missing cell → `not_reported` (`missing_cell`); `NOT_REPORTED` text → `not_reported`.
  - A malformed reply → row `failed` (`malformed`) with no cells, the next aspect still runs, nothing raises.
  - Every paper below the threshold for an aspect → row `not_reported` cells with **no** `generate` call.
  - Saving and reuse: a second `compare` with the same papers and aspects in another order → 0 requests; `retry_aspects=["datasets"]` re-runs only that row (1 `generate` call); `comparison_plan` = number of aspects.
  - Events: `plan`, then per aspect `progress` and per cell `part`, `row_failed` for a malformed row.
- [X] T018 [US3] Implement `compare()`, `saved_comparison()` and `comparison_plan()` in `paperpilot/service.py` (per-paper retrieval, numbering, `parse_row`, per-cell `review_reply(allowed=…)`, saving through the results cache), so T017 passes.

### US5 (P2): request plan, pre-check and stop rules (ADR-0009)

- [X] T019 [US5] Create failing tests in `tests/test_runs.py` (real `llm.generate` over `fake_llm.FakeClient` where the counter matters, `ScriptedLLM` otherwise):
  - **Pre-check:** with `DAILY_REQUEST_LIMIT=10` and 6 requests counted, `summarize` raises `DailyLimitError` before any request (FakeClient calls == 0); `compare` with 5 aspects likewise.
  - **Accounting:** a summary's first attempts never exceed its plan; with a scripted 429 then success on one facet, `requests == {planned: 6, retries: 1}` and the shared usage counter rose by 7.
  - **Stop rules:** a `DailyLimitError` or `RateLimitedError` raised in the third facet → facets 1–2 kept, 3–5 and the TL;DR `not_started` with the reason, no further `generate` call, and the partial summary saved; `LLMError(reason="busy")` likewise; `cut_off` does **not** stop the run.
  - **Events:** `retry_wait` events carry the `part` being retried.
- [X] T020 [US5] Implement the plan, pre-check and stop rules in `paperpilot/service.py` (`RequestPlan`, `_run_parts` shared by `summarize` and `compare`), so T019 passes.

**Checkpoint (engine)**: full `pytest` passes; the `ask()` tests are unchanged since T004.

---

## Phase 4: API (by story priority)

### US1: summary stream

- [X] T021 [P] [US1] Create failing tests in `tests/api/test_summaries_api.py` (all writes send `X-PaperPilot: 1`):
  - `GET /api/summaries` lists papers with `summary.status` (`none` before any summary) and `plan.max_requests == 6`.
  - `POST /api/summaries/{id}` streams `plan`, per-part `progress` and `part`, then `summary` last; the final body matches `data-model.md`.
  - No event before a part's `part` event contains that part's reply text (scripted sentinel text).
  - Pre-stream errors as plain JSON: `404 unknown_paper`, `422 invalid_request` (bad `retry_parts`).
  - No response contains the key, a traceback or provider text.
- [X] T022 [US1] Implement `GET /api/summaries` and `POST /api/summaries/{paper_id}` in `api/routes.py` with `SummarizeIn`, `summary_body` and `part_body` in `api/schemas.py`, streaming through `api/streams.run_streaming`, so T021 passes.

### US2: saved summaries over HTTP

- [X] T023 [US2] Add failing tests to `tests/api/test_summaries_api.py`:
  - `GET /api/summaries/{id}` → `404 not_saved` (with `plan`) before generation; after it, `200` with `status: current`, `created_at`, `model`; a second `POST` without `regenerate` streams only `summary` with 0 requests.
  - After a model change, `GET` returns `status: stale`, `stale_reason: model_changed`; after `DELETE /api/papers/{id}` it returns `404 unknown_paper`.
  - `regenerate: true` and `retry_parts: ["method"]` behave as in T011 through the stream.
- [X] T024 [US2] Implement `GET /api/summaries/{paper_id}`, the `not_saved` kind and the `regenerate`/`retry_parts` body fields in `api/routes.py`, `api/schemas.py` and `api/errors.py`, so T023 passes.

### US4: part states over HTTP

- [X] T025 [US4] Add failing tests to `tests/api/test_summaries_api.py`: scripted held-back, not-reported, cut-off and TL;DR-rejected parts arrive as `part` events with `state`, `reason`, `citations`, and `rejected_text` only for `held_back`; the stream still ends with `summary`.
- [X] T026 [US4] Complete `part_body` serialization in `api/schemas.py` so T025 passes (if T025 already passes, record the mutation run in the commit, as T043 of Feature 3).

### US3: comparisons over HTTP

- [X] T027 [P] [US3] Create failing tests in `tests/api/test_comparisons_api.py`:
  - `POST /api/comparisons` with 2 papers and 3 aspects streams `plan` (`max_requests: 3`), per-aspect `progress`, per-cell `part`, `row_failed` for a malformed row, then `comparison`.
  - `422 invalid_request` for 1 or 5 papers, duplicates, no or unknown aspects; `404 unknown_paper`.
  - `GET /api/comparisons?papers=b,a&aspects=results,method` finds the saved comparison regardless of order; `404 not_saved` otherwise.
  - `retry_aspects` re-runs one row.
- [X] T028 [US3] Implement `GET`/`POST /api/comparisons` in `api/routes.py` with `CompareIn` and `comparison_body` in `api/schemas.py`, so T027 passes.

### US5: plan, limits and one model task at a time

- [X] T029 [US5] Create failing tests in `tests/api/test_runs_api.py`, and update `tests/api/test_ask.py` for the rename:
  - While a scripted summary is held mid-run, `POST /api/ask` and `POST /api/comparisons` get `409 busy_task`; while a question runs, `POST /api/summaries/{id}` gets `409 busy_task`. In `tests/api/test_ask.py`, the one-question-at-a-time test now expects `busy_task` (the only change allowed there).
  - With fewer requests remaining than the plan, `POST` returns `429 daily_limit` with `needed`, `used`, `limit`, `resets_at` before the stream and sends no request.
  - A run stopped by `DailyLimitError` mid-way ends with `summary` whose remaining parts are `not_started`.
- [X] T030 [US5] Implement `model_lock` in `api/state.py` (replacing `question_lock`), the `busy_task` kind and `daily_limit.needed` in `api/errors.py`, and update `specs/003-web-app/contracts/web-api.md` (`busy_question` → `busy_task`), so T029 passes.

### Checkpoint 7 (real; plan 10 requests, cap 20)

- [X] T031 [US4] Create `scripts/checkpoint_7_summaries.py` with the run infrastructure and part `states` (0 requests):
  - Reuses `scripts/request_budget.py`; prints the plan table first (`summary` 6, `reopen` 0, `compare` 3, `not-reported` 1, `states` 0 = 10, cap 20) and `scripts/usage.py`'s figure, and refuses to start real parts when fewer than 10 requests remain.
  - Part `states` runs the engine in-process over a temporary library with a scripted model (real clients and the key endpoint blocked, as checkpoint 6 `states`): a held-back section, a not-reported section, a cut-off section, a malformed comparison row and a rejected TL;DR, each with its designed state and the rest of the summary or table intact.
  - Prints planned requests, retries and totals per part and in all, and FAILs on unplanned requests or totals above 2 × plan.
- [X] T032 [US1] Add parts `summary` and `reopen` to `scripts/checkpoint_7_summaries.py`:
  - `summary`: regenerates the LoRA summary through the API (plan 6); checks every shown citation is valid and opens (`GET /api/passages/{id}` and the PDF at the cited page); prints tokens per part against `MAX_OUTPUT_TOKENS`.
  - `reopen` (US2): `GET /api/summaries/{lora}` returns it in < 1 s and `GET /api/usage` is unchanged (0 requests).
  - Prints every claim (each sentence of each part) with its citations and, per citation, the paper, section, page and the first 200 characters of the passage; writes the same list to `docs/verification/checkpoint-7-<date>.md` with empty **Verdict** and **Fault (retrieval / model)** columns.
- [ ] T033 [US3] Add parts `compare` and `not-reported` to `scripts/checkpoint_7_summaries.py`:
  - `compare`: BERT vs RAG on Method, Datasets, Results (plan 3); every shown cell citation valid and from the cell's own paper; claims appended to the verification file.
  - `not-reported`: BERT vs RAG on Limitations (plan 1); PASS with at least one `not_reported` cell; if none, prints the cells and their citations as INFO (the `states` part still demonstrates the state, research R11).
  - Prints the malformed-row count.

**Checkpoint (API)**: full `pytest` passes; `python scripts/checkpoint_7_summaries.py states` passes with 0 requests.

---

## Phase 5: Frontend (by story priority)

### Shared shell

- [X] T034 [P] Create failing tests in `frontend/tests/app-shell.test.tsx` (extend): the header has four tabs Ask, Library, Summarize, Compare with `aria-current` on the active one; the `busy_task` copy ("PaperPilot is still working on another answer, summary or comparison") replaces `busy_question` in `frontend/tests/states.test.tsx` expectations.
- [X] T035 Implement the four tabs in `frontend/components/app/Header.tsx` and the `busy_task` copy in `frontend/lib/errorKinds.ts`, so T034 passes.

### US1 (P1): summarize a paper

- [X] T036 [P] [US1] Create failing tests in `frontend/tests/summary.test.tsx` (mocked `fetch`, streamed events):
  - The cost line reads "uses 6 requests · N left today" before starting; nothing is posted until the researcher confirms.
  - Progress per part ("Reading method passages", "Writing method", "Checking method"); a part's text appears only when its `part` event arrives.
  - The result shows the TL;DR card ("Built only from the verified sections below…") and five section cards in order with "4 passages read"; citation chips open `SourceViewer` at the cited passage (Feature 3 component).
  - "All citations verified" only when every part is `verified`.
  - The Library card's **Summarize** button links to `/summarize/<paper_id>`.
- [X] T037 [US1] Implement `frontend/app/summarize/[paperId]/page.tsx`, `frontend/components/summary/SummaryView.tsx`, `TldrCard.tsx`, `SectionCard.tsx`, `CostButton.tsx`, `frontend/lib/useSummary.ts` (POST stream over `postEventStream`), and the Summarize button in `frontend/components/library/PaperCard.tsx`, so T036 passes.
- [X] T038 [US1] Add test "F4 US1 summary" to `frontend/e2e/smoke.spec.ts` (fake backend replaying summary events from `frontend/e2e/fixtures.ts`): start from the Library card, see progress, then the TL;DR and five sections; open a citation in the viewer.

### US2 (P1): saved summaries

- [X] T039 [P] [US2] Create failing tests in `frontend/tests/summarize-picker.test.tsx`:
  - `/summarize` lists papers with their summary status (none, saved with time, "earlier model" for stale).
  - A saved summary opens with "Saved 2 hours ago · reopening cost 0 requests" and posts nothing.
  - A stale summary is labelled with its reason and is not marked "All citations verified" as current.
  - **Regenerate summary** shows the cost and asks for confirmation; on success the view is replaced; on failure the old summary stays.
  - A failed part offers "Retry this section" with its cost (e.g. "uses 2 requests").
- [X] T040 [US2] Implement `frontend/app/summarize/page.tsx` (picker), saved and stale states, regenerate and part retry in `frontend/components/summary/` and `frontend/lib/useSummary.ts`, so T039 passes.
- [X] T041 [US2] Add test "F4 US2 reopen" to `frontend/e2e/smoke.spec.ts`: open a saved summary from the Summarize tab with no POST sent; regenerate with confirmation.

### US4 (P1): per-part states

- [X] T042 [P] [US4] Create failing tests in `frontend/tests/part-states.test.tsx`:
  - `not_reported` reads "Not reported in the retrieved passages." with a search icon; the other sections render normally.
  - `held_back` shows the app's own warning (e.g. "Held back: this section cited passage 14, but only passages 9–12 were provided.") and "View the unverified text" reveals `rejected_text` labelled "Not verified" with the invalid numbers marked; never the engine's warning string.
  - `failed` with `cut_off` shows "The model's answer was cut off" and a retry; `not_started` shows why (daily limit, long wait, busy).
  - A held-back TL;DR shows its problem in plain words while the sections stay visible.
- [X] T043 [US4] Implement `frontend/components/summary/PartState.tsx` (shared by sections, TL;DR and cells) with copy in `frontend/lib/errorKinds.ts`, reusing the Feature 3 `HeldBack` marking, so T042 passes.
- [X] T044 [US4] Add test "F4 US4 part states" to `frontend/e2e/smoke.spec.ts`: a summary with one not-reported and one held-back section, the rest verified.

### US3 (P2): compare papers

- [ ] T045 [P] [US3] Create failing tests in `frontend/tests/compare.test.tsx`:
  - Papers 2–4 (chips, "+ Add paper"), aspects from the fixed five (all selected by default); "Compare papers" is disabled with the reason for 1 paper, 5 papers or no aspect.
  - The cost line reads "uses K requests, 1 per aspect · N left today".
  - Progress per aspect; cells appear only from `part` events; a table with one column per paper and one row per aspect, arXiv IDs in the header.
  - Cell citations open `SourceViewer`; a `row_failed` row shows "This row couldn't be read" with "Retry this row (1 request)".
  - The footer reads "8 of 10 cells verified" and "Passages were retrieved from each paper separately…".
  - A saved comparison of the same papers and aspects opens with 0 requests.
- [ ] T046 [US3] Implement `frontend/app/compare/page.tsx`, `frontend/components/compare/CompareForm.tsx`, `CompareTable.tsx`, `CompareCell.tsx` and `frontend/lib/useComparison.ts`, so T045 passes.
- [ ] T047 [US3] Add test "F4 US3 compare" to `frontend/e2e/smoke.spec.ts`: pick BERT and RAG, run, see the table with a not-reported cell and a held-back cell; at 375 px the table scrolls inside its own container, not the page.

### US5 (P2): cost and limits

- [ ] T048 [P] [US5] Create failing tests in `frontend/tests/cost-limits.test.tsx`:
  - With fewer remaining requests than the cost, the start button is disabled and the daily-limit state explains when requests resume; saved results still open.
  - A `429 daily_limit` with `needed` before the stream shows the daily-limit state, not a generic error.
  - `retry_wait` for a part shows the Feature 3 countdown inside that part's card.
  - `409 busy_task` shows the busy copy.
  - The usage meter updates after a run from the result's request totals or `/api/usage`.
- [ ] T049 [US5] Wire limits into `frontend/components/summary/CostButton.tsx`, `useSummary.ts` and `useComparison.ts` (reusing `DailyLimit`, `Busy` and `useUsage`), so T048 passes.
- [ ] T050 [US5] Add test "F4 US5 cost and limits" to `frontend/e2e/smoke.spec.ts`: at 50/50 the Summarize button is disabled with the daily-limit state, and a saved summary still opens.

---

## Phase 6: Polish and cross-cutting concerns

- [ ] T051 [P] Extend `frontend/e2e/smoke.spec.ts`: no sideways scrolling at 375 px on the Summarize picker, a summary, the Compare form and table; a keyboard-only pass that starts a summary, opens a citation, closes it with Escape and runs a comparison (SC-010).
- [ ] T052 [P] Extend `scripts/checkpoint_6_web.py` part `boundary`: `POST /api/summaries/{id}` and `POST /api/comparisons` are refused without `X-PaperPilot: 1` and from a foreign origin, with no model request; part `secrets` checks `git check-ignore data/library/results.sqlite3`.
- [ ] T053 [P] Update `docs/known-limitations.md`: rename the section to "Summaries and comparison", and add free-model JSON rows that may need a retry, TL;DR number-check false positives (e.g. paraphrased units), stale results kept for reading until replaced, and the plan's maximum refusing runs that would have needed fewer requests.
- [ ] T054 Run the full quickstart (`specs/004-summaries-comparison/quickstart.md`) and fix any drift:
  - `pytest`, `npm --prefix frontend run typecheck`, `npm --prefix frontend test`, `npm --prefix frontend run test:e2e`.
  - `python scripts/usage.py` (≥ 10 requests left), then `python scripts/checkpoint_7_summaries.py` with all parts (plan 10, cap 20); show its printed counts.
  - Commit the generated `docs/verification/checkpoint-7-<date>.md` with its claims list; the **Verdict** and **Fault** columns are left for the researcher's hand check (SC-002).
  - Record pass/fail, request totals, tokens per part and SC-001–SC-010 results in the PHR.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (T001–T002)** → **Foundational (T003–T004)** → **Engine (T005–T020)** → **API
  (T021–T033)** → **Frontend (T034–T050)** → **Polish (T051–T054)**.
- Within a layer, stories run in the order US1 → US2 → US4 → US3 → US5.

### Story dependencies

- **US1** needs T004 (shared validator) → T008 (summarize) → T022 (stream) → T037 (screen).
- **US2** needs US1's `summarize` (T008) and the cache (T010) → T024 → T040.
- **US4** needs US1's `summarize` (T008) → T014 → T026 → T043; its frontend `PartState` is reused by US3's cells.
- **US3** needs T004 and the cache (T010) → T018 → T028 → T046 (uses T043's `PartState`).
- **US5** needs US1 and US3 (`_run_parts` covers both) → T020 → T030 → T049.
- **Checkpoint 7** needs the API for its real parts (T031 needs T026; T032 needs T024; T033 needs T028).

### Within each story

- Test task first and failing (or passing with a recorded mutation run), then the implementation
  task, then the next pair; one commit per task.

### Parallel opportunities

- **Setup:** T001 and T002.
- **Engine:** T005 (prompt tests) with T009 (cache tests) and T015 (row prompt tests): different
  files, no shared state.
- **API:** T021 with T027 (different test files).
- **Frontend:** T034, T036, T039, T042, T045, T048 are test files that can be written in
  parallel; their implementations follow in story order.
- **Polish:** T051, T052, T053.

## Parallel Example: Engine prompts and cache

```text
T005 tests/test_prompts_summary.py   (facets, builders, check_tldr)
T009 tests/test_results_cache.py     (keys, staleness, invalidation, two processes)
T015 tests/test_prompts_compare.py   (row prompt, parse_row)
→ then T006, T010, T016 (prompts.py twice → run T006 then T016; library.py independent)
```

## Implementation Strategy

### MVP (US1 + US2 + US4, all P1)

1. Setup and Foundational (T001–T004): the generalised validator with `ask()` untouched.
2. Engine US1, US2, US4 (T005–T014), API US1, US2, US4 (T021–T026), checkpoint parts `states`,
   `summary`, `reopen` (T031–T032), frontend shell, US1, US2, US4 (T034–T044).
3. Stop and validate: a LoRA summary with cited sections, reopened at no cost (7 real requests
   at most: 6 + 0, plus the `states` part at 0).

### Incremental delivery

- Add US3 (comparison) next, then US5 (cost and limits), then Polish and the full checkpoint.

### Request plan for checkpoint 7

| Part | Planned requests |
|---|---|
| summary (LoRA) | 6 |
| reopen | 0 |
| compare (BERT vs RAG: Method, Datasets, Results) | 3 |
| not-reported (BERT vs RAG: Limitations) | 1 |
| states (scripted) | 0 |
| **Total** | **10** (cap 20 with retries) |

## Notes

- [P] tasks touch different files and depend on no incomplete task.
- Every commit message names its files and ends with the Co-Authored-By line.
- Mark each task [X] here when its commit lands.
- The hand verification of claims (SC-002) is the researcher's step; T054 prepares the record.
