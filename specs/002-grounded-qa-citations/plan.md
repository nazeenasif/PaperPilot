# Implementation Plan: Grounded Question Answering with Citations

**Branch**: `002-grounded-qa-citations` | **Date**: 2026-10-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-grounded-qa-citations/spec.md`

## Summary

`service.ask(question, paper_ids, k, history)` answers questions from the Feature 1 library.
It optionally rewrites a follow-up into a standalone question (last 6 turns), retrieves the top
k passages with Feature 1 search, drops passages below a calibrated relevance threshold
(provisional 0.60), and — only if passages remain — asks the model through one
OpenAI-compatible client (`llm.py`, the single LLM boundary; default OpenRouter with the
pinned free model `google/gemma-4-31b-it:free`) to answer from numbered, tag-delimited
passages with [n] citations. Replies are
checked in code: not-found detection, citation validation (invalid or missing → exact
not-found sentence plus warning), and an uncited-sentence warning. Retries honour the
server's `Retry-After` / `X-RateLimit-Reset`; cut-off output (`finish_reason == "length"`) is a
clear error; errors are readable and scrubbed of the API key. Details in
[research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (uv venv)
**Primary Dependencies**: Feature 1 stack + `openai` (3.37.0 installed and verified; pinned
with the other direct dependencies). `google-genai` was removed from the environment.
**Storage**: none new (reads the Feature 1 ChromaDB library)
**Testing**: pytest offline (fake LLM, fake embedder, generated PDFs); checkpoint scripts 4–5
call the real model
**Target Platform**: Windows 10/11, local CPU, OpenRouter free models over HTTPS (any
OpenAI-compatible endpoint by settings)
**Project Type**: single Python package + scripts
**Performance Goals**: typical answer < 15 s without rate limiting (SC-008); retrieval as in
Feature 1 (< 2 s warm)
**Constraints**: OpenRouter free limits 20/min and 50/day (1,000/day after $10 lifetime
credits, research R12); reasoning tokens count against `max_tokens` (R2); API key never in
output, logs, errors or commits
**Scale/Scope**: one researcher, ≤ 2 LLM calls per question, tens of papers

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Plain, typed Python | Python 3.12, no LangChain; `openai` client only; typed public functions with docstrings | ✅ |
| II. Modular package, single LLM boundary | `prompts`, `llm`, `service` added as defined in v1.1.0; only `llm.py` imports `openai`; `service` calls `library` | ✅ |
| III. OpenAI-compatible LLM, free tier by default (v1.2.0) | one OpenAI-compatible client; `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` from `config`; default OpenRouter + pinned `:free` model; no paid default; swapping providers needs settings only | ✅ |
| IV. Local embeddings, persistent store | reused unchanged from Feature 1 | ✅ |
| V. Grounded answers (NON-NEGOTIABLE) | numbered passages, [n] citations, code validation; invalid or missing citations → exact not-found; threshold before any LLM call; `NOT_FOUND` defined once in `prompts` | ✅ |
| VI. Secrets and data hygiene | `LLM_API_KEY` from `.env` only, `repr=False`, masked in `describe()`, scrubbed from errors, `git grep` check in checkpoint 4; `.env.example` placeholders only | ✅ |
| VII. Testable checkpoints, measured quality | pure logic unit-tested (prompts, citations, not-found, retries, config); checkpoints 4–5; probe answers recorded; full eval harness deferred | ⚠ justified below |
| VIII. Simplicity, small commits | no framework, no structured-output schema, one client for every provider; one commit per task | ✅ |

**Post-design re-check**: unchanged; the design adds no modules beyond Principle II's list.

## Project Structure

### Documentation (this feature)

```text
specs/002-grounded-qa-citations/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/answer-api.md
├── checklists/requirements.md
└── tasks.md            # /sp.tasks
```

### Source Code (repository root)

```text
paperpilot/
├── config.py        # + llm_provider, llm_base_url, llm_api_key (hidden), llm_model, relevance_threshold, llm_reasoning_effort
├── errors.py        # + LLMError
├── prompts.py       # NEW: NOT_FOUND, instructions, Turn, NumberedPassage, CitationReport, builders, parsers
├── llm.py           # NEW: generate() via one OpenAI-compatible client, retry_wait(), retries, key scrubbing
├── service.py       # NEW: Answer, ask() orchestration
├── library.py       # unchanged (Feature 1)
├── store.py         # unchanged
└── ingest.py        # unchanged

scripts/
├── calibrate_threshold.py        # NEW: top scores for on/off-topic sets -> eval/threshold_calibration.md
├── checkpoint_4_answer.py        # NEW: cited answer, not-found, filter, citation checks, timings, secret scan
└── checkpoint_5_conversation.py  # NEW: follow-up rewrite, probe questions -> eval/probe_answers.md

tests/
├── test_settings.py   # + LLM settings, masking, threshold validation
├── test_prompts.py    # NEW: prompt building/escaping, not-found, citations, uncited sentences, rewrite cleaning
├── test_llm.py        # NEW: retry_wait headers/backoff, retries with a fake client, length cut-off, 200-with-error, key scrubbing (no network)
└── test_service.py    # NEW: ask() with fake llm + fake embedder: threshold, no-LLM not-found, rejection, filter, rewrite, timings

eval/
├── threshold_calibration.md   # generated by calibrate_threshold.py
└── probe_answers.md           # generated by checkpoint 5
```

**Structure Decision**: same single package; three new modules exactly as named in
Principle II. Turn, NumberedPassage and CitationReport live in `prompts` because they define
the text contract with the model; `service` re-exports `Turn` for callers.

## Key Decisions (rationale in research.md)

ADRs: [ADR-0003 LLM Boundary and Retry Policy](../../history/adr/0003-llm-boundary-and-retry-policy.md) (1–3),
[ADR-0004 Grounding and Citation Validation](../../history/adr/0004-grounding-and-citation-validation.md) (4–8).

1. One `openai` client (`max_retries=0`), base URL/key/model from settings; default OpenRouter
   + pinned `google/gemma-4-31b-it:free`; temperature 0, `max_tokens` 2048, optional
   `reasoning.effort`; `finish_reason == "length"` → `LLMError` (R1, R2).
2. Retries: 4 attempts; `Retry-After` else `X-RateLimit-Reset` (≤ 60 s) else 2/4/8 s; only
   408/429/5xx/timeouts and 200-with-error bodies (R3).
3. Key hidden in settings, scrubbed from errors, scanned by checkpoint 4 (R4).
4. Rules in `system_instruction`; passages as escaped `<passage>` tags (R5).
5. Lenient not-found detection mapped to the exact sentence (R6).
6. Citation parsing with groups/ranges; invalid or none → not-found + warning; uncited
   sentences → warning only (R7, clarifications Q1/Q1b).
7. Threshold 0.60 provisional, calibrated with evidence; never rejects on-topic (R8, Q2).
8. Rewrite only with history, last 6 turns, fallback to original (R9).

## Risks

1. **Free-tier limits** (20/min, 50/day) make checkpoints slow and cap repeated runs — honour
   rate-limit headers, ≤ 2 calls per question, print waits; evaluation runs need the 1,000/day
   tier (R12).
2. **Free-model churn and reasoning** — the pinned model can disappear (checkpoint 4 checks it
   is listed) and reasoning can use up the output budget (2048 tokens, clear `length` error,
   optional `LLM_REASONING_EFFORT`).
3. **Threshold too strict for vague questions** — calibration set includes vague questions;
   setting is configurable; never-reject-on-topic rule.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| No full eval harness run although answers and prompts are introduced (Principle VII) | The spec puts the eval harness out of scope; it is the next feature and will use the probe baseline | Checkpoints 4–5 plus recorded probe answers (`eval/probe_answers.md`) and threshold calibration provide the interim quality measurement |
