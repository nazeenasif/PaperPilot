# Data Model: Grounded Question Answering with Citations

**Feature**: 002-grounded-qa-citations | **Date**: 2026-10-24

All types are frozen dataclasses. Nothing new is persisted: answers and conversations live in
memory; the library from Feature 1 is read only.

## Settings additions (`config.py`)

| Field | Env var | Type | Default | Validation |
|---|---|---|---|---|
| llm_provider | `LLM_PROVIDER` | str | `openrouter` | label; selects the default base URL and appears in error messages |
| llm_base_url | `LLM_BASE_URL` | str | `""` → `https://openrouter.ai/api/v1` for `openrouter` | required (explicitly) for any other provider label |
| llm_api_key | `LLM_API_KEY` | str | `""` | required when asking; `repr=False`; `describe()` shows `set (hidden)` / `not set` |
| llm_model | `LLM_MODEL` | str | `nvidia/nemotron-3-ultra-550b-a55b:free` | non-empty |
| relevance_threshold | `RELEVANCE_THRESHOLD` | float | `0.59` (calibrated) | 0 ≤ value ≤ 1 |
| llm_reasoning_effort | `LLM_REASONING_EFFORT` | str | `""` | optional; sent as `reasoning.effort` when set |
| llm_timeout_seconds | `LLM_TIMEOUT_SECONDS` | int | `60` | ≥ 1; per model request (research R13) |

Feature 1 behaviour is unchanged when the LLM settings are absent.

## Turn

| Field | Type | Notes |
|---|---|---|
| role | str | `"user"` or `"assistant"` |
| text | str | message text |

## NumberedPassage

| Field | Type | Notes |
|---|---|---|
| number | int | citation number, 1..n in order of score |
| passage_id, paper_id, title, section, page, score, text | | from Feature 1 `SearchResult` |

## CitationReport

| Field | Type | Notes |
|---|---|---|
| valid | list[int] | cited numbers that map to a provided passage (sorted, unique) |
| invalid | list[int] | cited numbers outside 1..n |
| uncited_sentences | list[str] | sentences without any citation |

## LLMReply (`llm.py`)

| Field | Type | Notes |
|---|---|---|
| text | str | model output |
| input_tokens | int \| None | `usage.prompt_tokens` |
| output_tokens | int \| None | `usage.completion_tokens` (includes reasoning tokens) |
| reasoning_tokens | int \| None | `usage.completion_tokens_details.reasoning_tokens` |
| attempts | int | 1 + retries |
| seconds | float | wall time including retries |

## Answer (`service.py`, returned by `ask`)

| Field | Type | Notes |
|---|---|---|
| question | str | as asked |
| standalone_question | str | equals `question` when no rewrite |
| rewrite_applied | bool | False when no history or rewrite failed |
| text | str | the answer, or exactly `NOT_FOUND` |
| not_found | bool | True when `text == NOT_FOUND` |
| passages | list[NumberedPassage] | passages given to the model (empty if none passed the threshold) |
| citations | CitationReport | empty report for not-found answers from the threshold |
| warning | str \| None | invalid/missing citations (with original answer text) or uncited sentences |
| rejected_answer | str \| None | the model's original text when it was replaced by `NOT_FOUND` |
| fallback_reason | str \| None | why the answer is `NOT_FOUND`: `no_passages`, `below_threshold`, `model_not_found`, `invalid_citations`, `no_citations`; `None` for a real answer |
| rewrite_fallback_reason | str \| None | why the original question was used despite history: `rewrite_failed`, `rewrite_empty`; `None` otherwise |
| word_count | int | words in `text`, not counting citation markers like [2]; reported, never enforced |
| llm_calls | int | 0, 1 (answer) or 2 (rewrite + answer) |
| timings | dict[str, float] | `rewrite`, `retrieve`, `generate` (seconds; 0.0 when skipped) |
| tokens | dict[str, int] | `input`, `output`, `reasoning` summed over calls; keys omitted when unknown |

## Flow and states

```
question ─► [history?] rewrite ─► retrieve (k, filter) ─► threshold
   ├─ no passages left ─────────────────────────────► NOT_FOUND (llm_calls counts rewrite only)
   └─ passages ─► generate ─► is_not_found? ─ yes ──► NOT_FOUND
                                 └─ no ─► citations: invalid or none ─► NOT_FOUND + warning + rejected_answer
                                                      └─ all valid ───► answer (+ uncited-sentence warning)
```
