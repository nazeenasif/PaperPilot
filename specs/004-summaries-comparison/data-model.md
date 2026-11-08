# Data Model: Paper Summaries and Cross-Paper Comparison (Feature 4)

Engine dataclasses live in `paperpilot/service.py` (results) and `paperpilot/prompts.py`
(checks); the saved form is the JSON of these objects in `<LIBRARY_DIR>/results.sqlite3`
(research R6). Names below are the API field names.

## Part

One summary section, the TL;DR, or one comparison cell.

| Field | Type | Notes |
|---|---|---|
| part | str | `problem`, `method`, `data`, `results`, `limitations`, `tldr`; for cells `"<aspect>:<paper_id>"` |
| state | enum | `verified`, `not_reported`, `held_back`, `failed`, `not_started` |
| text | str \| null | checked text with `[n]` citations; `null` unless `verified` |
| citations | {valid: [int], invalid: [int], uncited_sentences: [str]} | as for answers |
| warning | str \| null | why it was held back (engine wording; the UI shows its own copy, see contracts) |
| rejected_text | str \| null | the unverified model text, only when `held_back` |
| reason | str \| null | for `not_reported`: `below_threshold`, `no_passages`, `model_not_found`, `no_citations`, `missing_cell`, `no_verified_sections`; for `failed`/`not_started`: `cut_off`, `empty`, `malformed`, `model_busy`, `daily_limit`, `rate_limited`, `model_unavailable` |
| sources | [str] | TL;DR only: the sections each sentence traced to, per sentence (research R3) |
| built_from | [str] | TL;DR only: the sections whose text it used |
| built_without | [str] | TL;DR only: sections it went without (failed, held back, or regenerated since) |
| passages | [int] | numbers of the passages given for this part |
| requests | {planned, retries} | requests this part used (0 for not reported without a request) |
| tokens | {input?, output?, reasoning?} | as reported by the provider, for cut-off parts too |

Rules (FR-011):
- `verified` ⇔ text has ≥ 1 citation, all in `passages` (cells: that paper's passages for that
  row), and is not the not-found / not-reported sentence. TL;DR: also research R3 steps 2–4.
- invalid citation ⇒ `held_back` (text `null`, `rejected_text` set).
- no citation, not-found sentence, missing cell, or no relevant passages ⇒ `not_reported`.
- `failed` parts can be retried; `not_started` parts are retried with them.

State transitions: `pending → verified | not_reported | held_back | failed`; a run stopped by a
daily limit, long wait, busy model or unavailable model leaves later parts `not_started`. A retry
moves `failed`/`not_started` parts back to `pending`; a section retry leaves the TL;DR as it is,
marked `built_without` that section until the TL;DR is retried too.

## NumberedPassage (existing, Feature 2)

`number, passage_id, paper_id, title, section, page, score, text`. Numbered once per run
(FR-004): a passage retrieved for two facets or two rows keeps its first number.

## Summary

| Field | Type | Notes |
|---|---|---|
| paper_id | str | content ID (SHA-1 prefix of the PDF) |
| title, arxiv_id | str, str \| null | for the header |
| tldr | Part | |
| sections | [Part] × 5 | fixed order problem, method, data, results, limitations |
| passages | [NumberedPassage] | every passage numbered in this summary |
| plan | {max_requests} | 6 for a full run |
| requests | {planned, retries} | totals for the run that produced it |
| model, prompt_version, created_at | str, int, ISO UTC | FR-018 |
| status | enum | `current`, `stale` (with `stale_reason`: `model_changed`, `instructions_changed`, `passages_changed`) |
| verified_parts | int | e.g. "6 of 6" for the badge; the badge "All citations verified" only when every part is `verified` |

## Comparison

| Field | Type | Notes |
|---|---|---|
| paper_ids | [str] | 2–4, distinct, in the researcher's order for display; sorted in the key |
| papers | [{paper_id, title, arxiv_id, label}] | label `P1…P4` used in the prompt |
| aspects | [str] | subset of `problem, method, datasets, results, limitations`, in fixed order |
| rows | [{aspect, state: ok \| failed \| not_started, reason?, cells: [Part]}] | one row per aspect; a failed row (e.g. `malformed`) has no cells |
| passages | [NumberedPassage] | |
| plan, requests, model, prompt_version, created_at, status | as Summary | plan = number of aspects |
| verified_cells, total_cells | int | "8 of 10 cells verified" |

## SavedResult (SQLite row, research R6)

`kind, key, paper_ids, result (JSON of Summary or Comparison), model, prompt_version,
created_at`. Key = SHA-256 of `kind`, sorted paper IDs, each paper's passage fingerprint, sorted
aspects, prompt version and `LLM_MODEL`. Rows are deleted by `forget_results(paper_id)` on delete
and re-process.

## RequestPlan

`{max_requests: int, parts: [str]}` — computed before any request; the pre-check compares
`max_requests` with `llm.usage().remaining` (FR-021–FR-023).

## Facets and aspects (constants, `prompts.py`)

| Key | Summary label | Comparison label | Passages | Max words |
|---|---|---|---|---|
| problem | Problem | Problem | 4 / 3 per paper | 80 / 50 |
| method | Method | Method | 4 / 3 | 80 / 50 |
| data / datasets | Data | Datasets | 4 / 3 | 80 / 50 |
| results | Results | Results | 4 / 3 | 80 / 50 |
| limitations | Limitations | Limitations | 4 / 3 | 80 / 50 |
| tldr | TL;DR | — | from verified sections | 60, ≤ 3 sentences |
