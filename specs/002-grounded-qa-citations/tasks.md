---

description: "Task list for 002-grounded-qa-citations"
---

# Tasks: Grounded Question Answering with Citations

**Input**: Design documents from `/specs/002-grounded-qa-citations/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/answer-api.md, quickstart.md
**ADRs**: history/adr/0003-llm-boundary-and-retry-policy.md, history/adr/0004-grounding-and-citation-validation.md

**Tests**: Required for pure logic (constitution Principle VII). Unit tests are written BEFORE
the code they test and must fail first. **Unit tests never call the real API**: `llm.py` tests
use a scripted fake OpenAI client; `service.py` tests replace `llm.generate` with scripted
replies; an autouse fixture makes any attempt to build a real client fail the test. Only the
checkpoint scripts call OpenRouter.

**Request budget**: OpenRouter free models allow 50 requests/day without credits. Every
checkpoint prints the number of HTTP requests it made to the model (including retries) and
stops with FAIL if it exceeds its budget (checkpoint 4: 6, checkpoint 5: 12; calibration: 0).
A full run of both checkpoints uses about 10 requests.

**Organization**: Grouped by user story in priority order (US1, US2 P1; US3, US4, US5 P2).
Every task is one commit; public functions get type hints and short docstrings.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 map to the user stories in spec.md

---

## Phase 1: Setup

- [X] T001 Add `openai==3.37.0` and `tenacity==9.1.4` to `requirements.txt` (tenacity is required by chromadb and was moved by the earlier google-genai install; pin it so installs are reproducible), confirm `google-genai` is absent, and run `uv pip install --python .venv\Scripts\python.exe -r requirements.txt` (no changes expected) and `pytest` (183 pass)

---

## Phase 2: Foundational (LLM settings, errors, the LLM boundary)

**Purpose**: everything every story needs to call the model safely. No story can start before
this phase ends.

- [X] T002 [P] Add failing tests to `tests/test_settings.py` for the new settings (data-model.md): defaults `LLM_PROVIDER=openrouter`, `LLM_BASE_URL=""`, `LLM_API_KEY=""`, `LLM_MODEL=google/gemma-4-31b-it:free`, `RELEVANCE_THRESHOLD=0.60`, `LLM_REASONING_EFFORT=""`; env overrides; `RELEVANCE_THRESHOLD` non-number and values outside 0–1 raise `SettingsError` naming the variable and value; `repr(settings)` never contains the key; `describe()` shows `LLM_API_KEY = set (hidden)` when set and `not set` otherwise, and never the key value; extend the existing `clean_env` fixture list with the new variable names
- [X] T003 [P] Add `LLMError(PaperPilotError)` ("the language model failed; message is one readable line with no secrets") to `paperpilot/errors.py`
- [X] T004 Implement the new fields in `paperpilot/config.py` (`llm_api_key` with `field(repr=False)`, float parsing for the threshold, masked `describe()`); make T002 pass
- [X] T005 [P] Create `tests/fake_llm.py` (helpers, not collected as tests) with a scripted fake OpenAI client: `FakeClient(responses)` exposing `client.chat.completions.create(**kwargs)` that records every call's kwargs and returns or raises the next scripted item; builders `ok(text, prompt_tokens=10, completion_tokens=20, reasoning_tokens=None)`, `no_usage(text)` (usage `None`), `length(reasoning_tokens=2000)` (`finish_reason="length"`, empty content), `error_body(code, message)` (a 200 response with an `error` object and no `choices`, built with `ChatCompletion.construct(...)` so it parses as loosely as the real SDK), `rate_limited(retry_after=None, reset_ms=None)` and `status_error(code)` (real `openai.RateLimitError` / `openai.APIStatusError` built with an `httpx2.Response` and `httpx2.Request`, since openai 3.37.0 uses `httpx2`), and `timeout()` (`openai.APITimeoutError`)
- [X] T006 Add an autouse fixture to `tests/conftest.py` that monkeypatches `paperpilot.llm._make_client` to raise `AssertionError("real LLM client created in a unit test")`, plus an `llm_env` fixture setting `LLM_API_KEY=sk-test-key-123` and default LLM settings via `monkeypatch.setenv`
- [X] T007 Write failing tests in `tests/test_llm.py` (uses T005/T006; no network): `retry_wait()` returns `Retry-After` seconds, else seconds until `X-RateLimit-Reset` (epoch ms), capped at 60, else 2/4/8 by attempt, and `None` for 400/401/403/404, for 402 without `Retry-After`, and for a `length` finish; `generate()` with `ok` returns `LLMReply` with text, tokens and `attempts=1`; `no_usage` gives `None` token fields; one `rate_limited(retry_after=3)` then `ok` → `attempts=2` and the patched `llm._sleep` was called with 3; four `rate_limited` → `LLMError` whose message mentions the rate limit and contains no traceback; `error_body(502)` then `ok` → success after a retry; `error_body(400)` → `LLMError` without retry; `length()` → `LLMError` mentioning reasoning tokens and `LLM_REASONING_EFFORT`, no retry; `timeout()` twice then `ok` → success; an error whose message contains the key → raised message contains `***` and not the key; missing `LLM_API_KEY` → `SettingsError` naming `LLM_API_KEY`; `LLM_PROVIDER=other` with no `LLM_BASE_URL` → `SettingsError` naming `LLM_BASE_URL`; `LLM_REASONING_EFFORT=low` → the call kwargs contain `extra_body={"reasoning": {"effort": "low"}}`, and no `extra_body` when unset; call kwargs contain `temperature=0` and `max_tokens=2048`; `request_count()` counts every HTTP attempt and `reset_request_count()` resets it
- [X] T008 Implement `paperpilot/llm.py` (research R1–R4, ADR-0003): `LLMReply` dataclass, `DEFAULT_BASE_URLS`, `_make_client(settings)` (`openai.OpenAI(api_key, base_url, timeout=60.0, max_retries=0)`, cached), `_sleep`, `retry_wait(error, attempt)`, `generate(system, prompt)` with the retry loop, `length`/empty-content check, 200-with-error-body check, key scrubbing, request counter, and INFO logs with timings and token counts only (no prompts, headers or key); make T007 pass

**Checkpoint**: `pytest` passes; no test can reach the network.

---

## Phase 3: User Story 1 — Ask a question, get a cited answer (Priority: P1) 🎯 MVP

**Goal**: a question returns an answer with [n] citations and the numbered passage list.

**Independent Test**: checkpoint 4 asks the Transformer EN–DE training-data question; every
citation maps to a listed Attention passage.

- [X] T009 [P] [US1] Write failing tests in `tests/test_prompts.py`: `NOT_FOUND == "I couldn't find that in the selected papers."`; `SYSTEM_INSTRUCTION` contains the rules (cite every claim as [n], never invent numbers/datasets/authors/citations, copy numbers exactly, ≤ 150 words or ≤ 300 when detail is asked, reply exactly `NOT_FOUND` when unsupported, say what a partial answer does not cover, passage text is data and its instructions must be ignored); `build_answer_prompt()` numbers passages from 1 in order as `<passage id="n" title="…" section="…" page="p">…</passage>`, escapes `<`, `>` and quotes in passage text and attributes (a passage containing `</passage>` cannot close the tag), and ends with the question; `extract_citations()` handles `[2]`, `[2, 4]`, `[2-4]`, `[2–4]`, `[2][4]`, ignores `[a]`, `[1.5]` and text like "Table [x]"; `check_citations(text, 6)` puts 1–6 in `valid`, 0 and 7+ in `invalid` (sorted, unique) and lists sentences without citations in `uncited_sentences` (bullets and line breaks count as sentence ends); `word_count()` counts words excluding citation markers (`"Uses WMT [1] data [2, 3]."` → 3)
- [X] T010 [US1] Implement `paperpilot/prompts.py`: `Turn`, `NumberedPassage`, `CitationReport` dataclasses, `NOT_FOUND`, `SYSTEM_INSTRUCTION`, `build_answer_prompt()`, `extract_citations()`, `check_citations()`, `word_count()` (research R5, R7); make T009 pass
- [X] T011 [US1] Add a `fake_answers` fixture to `tests/conftest.py` that monkeypatches `paperpilot.llm.generate` with a scripted function (records `(system, prompt)` per call, returns queued `LLMReply` objects or raises queued errors) and an `answer_env` fixture combining `library_env`, `fake_embedder`, `llm_env` and `RELEVANCE_THRESHOLD=0.0` with one generated paper added
- [X] T012 [US1] Write failing tests in `tests/test_service.py` (uses T011): `ask()` returns `Answer` with the scripted text, `passages` numbered 1..n with title, section, page, score and text, `citations.valid` matching the cited numbers, `llm_calls == 1`, `timings` keys `rewrite`/`retrieve`/`generate` (rewrite 0.0), `tokens` summed from the reply (keys omitted when the reply has no usage), `standalone_question == question`, `rewrite_applied is False`, `fallback_reason is None`, `rewrite_fallback_reason is None`, `word_count` equals `prompts.word_count(text)`; a scripted 400-word cited reply is returned unchanged and in full (no trimming in code); the prompt sent to the model contains every passage tag and the question; `k=2` sends at most 2 passages; empty or whitespace question raises `EmptyQueryError` and makes no call
- [X] T013 [US1] Implement `paperpilot/service.py`: `Answer` dataclass (data-model.md, including `fallback_reason`, `rewrite_fallback_reason`, `word_count`), re-export `Turn`, `ask(question, paper_ids=None, k=None, history=None)` performing retrieve (`library.search`) → number passages → `llm.generate(SYSTEM_INSTRUCTION, build_answer_prompt(...))` → `check_citations`, with timings and token totals; make T012 pass
- [X] T014 [US1] Create `scripts/checkpoint_4_answer.py` (US1 part): call `llm.reset_request_count()`, check the configured model is listed via a new `llm.model_is_listed()` (the provider's `/models` endpoint; only `llm.py` talks to the provider; not counted against the budget; fake-client tests in `tests/test_llm.py`) and print PASS/FAIL, ask "What recurrent models were state of the art for sequence modelling before the Transformer?" (its top passage contains the paper's own reference markers, exercising research R5b), print how many passages had markers removed, the answer, numbered passages (title, section, page, score), citation report, timings and tokens; print PASS/FAIL for ≥ 1 citation and all citations valid; print the word count as INFO, or WARN (not FAIL) above 165 words; print `LLM requests: N (budget 6)` and FAIL if over budget — **Checkpoint 4, US1 part** (SC-001, SC-010, SC-011)

---

## Phase 4: User Story 2 — Unsupported questions get the not-found sentence (Priority: P1)

**Goal**: off-topic or unsupported questions return exactly `NOT_FOUND`, without a model call
when no passage passes the threshold.

**Independent Test**: checkpoint 4 asks "What is the capital of France?" → exactly the
not-found sentence and 0 LLM requests.

- [X] T015 [P] [US2] Add failing tests to `tests/test_prompts.py` for `is_not_found()`: exact sentence; with surrounding quotes, whitespace or no final period; curly apostrophe (’); different case; reply that starts with the sentence and continues; a normal answer mentioning "couldn't find" mid-sentence is not not-found
- [X] T016 [P] [US2] Add failing tests to `tests/test_service.py`: with `RELEVANCE_THRESHOLD=0.99` → `text == NOT_FOUND`, `not_found`, `passages == []`, `llm_calls == 0`, `fallback_reason == "below_threshold"` and the fake was never called; with a threshold between passage scores only passages at or above it are sent; scripted reply `"\"I couldn't find that in the selected papers\""` → exactly `NOT_FOUND` with `fallback_reason == "model_not_found"`; empty library → `NOT_FOUND`, 0 calls, `fallback_reason == "no_passages"`
- [X] T017 [US2] Implement `is_not_found()` in `paperpilot/prompts.py` (research R6); make T015 pass
- [X] T018 [US2] Add the relevance threshold and not-found mapping to `ask()` in `paperpilot/service.py`; make T016 pass
- [ ] T019 [US2] Create `scripts/calibrate_threshold.py` (no LLM requests): search the library (k=6) for at least 6 on-topic questions (the 5 probe questions in `eval/probe_notes.md` plus vague ones such as "what dataset was used for evaluation?" and "what are the limitations?") and off-topic questions in three groups: at least 4 clearly off-topic (e.g. "What is the capital of France?"), at least 2 word-level near-misses that reuse the papers' words in another sense (e.g. "How do electrical transformers step down voltage?", "Who invented the BERT muppet character?"), and at least 2 topic-level near-misses that are in-domain but not answered by these papers (e.g. "How was GPT-4 trained?", "What is the context window of Claude?"); print each top score labelled on-topic / off-topic / word-level near-miss / topic-level near-miss; suggest the threshold as the lowest on-topic top score minus 0.03, rounded down to 2 decimals; report the rejection rate at the configured and suggested thresholds separately for each of the three off-topic groups (topic-level near-misses are expected to pass the threshold and be caught by the model's not-found rule); write `eval/threshold_calibration.md`, stating that the value is calibrated for bge-small-en-v1.5 on this library; print WARN if the suggestion differs from the configured default by more than 0.02 (FR-003, SC-003)
- [ ] T020 [US2] Extend `scripts/checkpoint_4_answer.py`: ask "What is the capital of France?"; PASS if the answer is exactly `NOT_FOUND` and the request counter did not change — **Checkpoint 4, US2 part** (SC-002)

---

## Phase 5: User Story 3 — Ask within selected papers (Priority: P2)

**Goal**: a paper filter limits passages, and therefore citations, to the selected papers.

**Independent Test**: checkpoint 4 asks the BERT pre-training question filtered to BERT; all
passages come from BERT.

- [ ] T021 [US3] Add failing tests to `tests/test_service.py` (two generated papers): filtered `ask()` sends only passages from the selected paper; an unknown paper ID raises `UnknownPaperError` before any model call; `paper_ids=[]` behaves like no filter
- [ ] T022 [US3] Pass `paper_ids` through `ask()` to `library.search` in `paperpilot/service.py`, making sure the filter is checked before any model call; make T021 pass
- [ ] T023 [US3] Extend `scripts/checkpoint_4_answer.py`: ask "What are the two pre-training tasks of BERT?" filtered to the BERT paper ID (looked up with `list_papers()`); PASS if every passage is from BERT and every citation is valid — **Checkpoint 4, US3 part** (SC-004)

---

## Phase 6: User Story 4 — Follow-up questions (Priority: P2)

**Goal**: follow-ups are rewritten into standalone questions from the last 6 turns.

**Independent Test**: checkpoint 5 asks "What is LoRA?" then "What are its limitations?"; the
standalone question names LoRA.

- [ ] T024 [P] [US4] Add failing tests to `tests/test_prompts.py`: `REWRITE_INSTRUCTION` asks for one standalone question, resolving pronouns, adding no facts; `build_rewrite_prompt(history, question)` includes only the last 6 turns (given 8, the first 2 are absent), labels roles and ends with the question; `clean_rewrite()` strips quotes, a leading "Standalone question:" prefix and extra lines, and returns `""` for empty output
- [ ] T025 [P] [US4] Add failing tests to `tests/test_service.py`: no history → no rewrite call (`llm_calls == 1`); with history → the first call uses `REWRITE_INSTRUCTION`, `library.search` receives the standalone question (spy), `standalone_question` and `rewrite_applied` are set, `llm_calls == 2`, `timings["rewrite"] > 0`; rewrite raising `LLMError` → original question used, `rewrite_applied is False`, `rewrite_fallback_reason == "rewrite_failed"`, answer still produced; rewrite returning empty text → same with `rewrite_fallback_reason == "rewrite_empty"`
- [ ] T026 [US4] Implement `REWRITE_INSTRUCTION`, `build_rewrite_prompt()` and `clean_rewrite()` in `paperpilot/prompts.py` (research R9); make T024 pass
- [ ] T027 [US4] Add the rewrite step with fallback to `ask()` in `paperpilot/service.py`; make T025 pass
- [ ] T028 [US4] Create `scripts/checkpoint_5_conversation.py` (US4 part): `reset_request_count()`, ask "What is LoRA?", then ask "What are its limitations?" with the first exchange as history; print both standalone questions, answers and citation reports; PASS if the second standalone question contains "LoRA" (case-insensitive) and its citations are valid; print `LLM requests: N (budget 12)` and FAIL if over — **Checkpoint 5, US4 part** (SC-005)

---

## Phase 7: User Story 5 — Invalid citations are caught (Priority: P2)

**Goal**: answers with invalid or missing citations become the not-found sentence plus a
warning; uncited sentences produce a warning only.

**Independent Test**: `review_reply("X [2]. Y [9].", 6)` returns `NOT_FOUND`, a warning naming
[9], and the original text — no model needed.

- [ ] T029 [US5] Add failing tests to `tests/test_service.py` for the pure helper `review_reply(text, passage_count) -> (answer_text, citations, warning, rejected_answer, fallback_reason)`: invalid number → `NOT_FOUND`, warning lists the invalid numbers, `rejected_answer` is the original, reason `invalid_citations`; no citations at all → `NOT_FOUND` with a "no citations" warning, reason `no_citations`; not-found replies in tolerant forms (exact, quoted, extra whitespace, no final period) → `NOT_FOUND`, reason `model_not_found`, no warning and never treated as "no citations"; all valid but one uncited sentence → original text kept, warning lists that sentence, `rejected_answer is None`; and through `ask()` with a scripted reply citing [9] of 1 passage → `Answer.text == NOT_FOUND`, `warning` and `rejected_answer` set
- [ ] T030 [US5] Implement `review_reply()` in `paperpilot/service.py` and use it in `ask()` (FR-008a, FR-009, ADR-0004); make T029 pass
- [ ] T031 [US5] Extend `scripts/checkpoint_4_answer.py` with an offline citation check (no LLM request): run `review_reply()` on a crafted answer citing [2] and [9] with 6 passages and on one with no citations; PASS if both become `NOT_FOUND` with warnings naming the problem — **Checkpoint 4, US5 part** (SC-001)

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T032 Extend `scripts/checkpoint_5_conversation.py`: ask the five probe questions from `eval/probe_notes.md` (no history), write `eval/probe_answers.md` with question, answer, citation report, passage list (title, section, page, score), warning, word count, LLM requests used, and an empty "Reviewer verdict" column; print PASS/FAIL for no invalid citation returned, and the word count as INFO or WARN above 165 (never FAIL); print INFO for Q2/Q4 reminding the reviewer that not-found or a limited partial answer is the correct outcome (FR-019, SC-006)
- [ ] T033 Add a secret check to `scripts/checkpoint_4_answer.py`: run `git grep --untracked -F -q <LLM_API_KEY value> -- . ":!.env"` and confirm `describe()` hides the key; print only PASS/FAIL, never the key; also confirm `.env` is ignored by git (`git check-ignore .env`) (SC-007)
- [ ] T034 [P] Add a "Question answering" section to `docs/known-limitations.md`: citation validation proves citations point to provided passages, not that they support the claim; threshold needs recalibration when papers, chunking or the model change; free models change and can be removed; free-tier limits (20/min, 50/day without credits) make repeated runs and evaluation impractical without credits; the uncited-sentence splitter can be noisy around abbreviations
- [ ] T035 Run `pytest`, `python scripts/calibrate_threshold.py`, `python scripts/checkpoint_4_answer.py` and `python scripts/checkpoint_5_conversation.py` per `specs/002-grounded-qa-citations/quickstart.md`; fix any drift in the quickstart; record total LLM requests, timings and SC results (including SC-008 typical answer time) in the PHR, and update `RELEVANCE_THRESHOLD`'s default in `paperpilot/config.py`, `.env.example` and research R8 if calibration suggests a different value (R8 keeps stating it is calibrated for bge-small-en-v1.5 on this library)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)** → **Foundational (T002–T008)** → user stories.
- **US1 (T009–T014)** needs Foundational. **US2 (T015–T020)** needs US1 (`ask()` exists).
- **US3, US4, US5** each need US1; they edit the same files (`service.py`, `test_service.py`,
  checkpoint scripts), so do them in order US3 → US4 → US5 after US2.
- **Polish (T032–T035)** needs all stories; T035 is last.

### Within Phases

- Foundational: T002, T003 and T005 in parallel; T004 after T002; T006 after T005; T007 after
  T005–T006; T008 after T003, T004 and T007.
- US1: T009 first (parallel with nothing else in `prompts`), T010; T011 → T012 → T013 → T014.
- US2: T015 and T016 in parallel; T017 after T015; T018 after T016–T017; T019 any time after
  T018; T020 after T018.
- US4: T024 and T025 in parallel; T026 → T027 → T028.

### Parallel Opportunities

- T002, T003, T005 (settings tests, errors, fake client).
- T015 with T016; T024 with T025 (different test files).
- T034 alongside T032–T033.

## Parallel Example: Foundational

```text
T002 tests/test_settings.py   (new settings tests)
T003 paperpilot/errors.py      (LLMError)
T005 tests/fake_llm.py         (scripted fake OpenAI client)
```

---

## Implementation Strategy

### MVP (US1 + US2, both P1)

1. T001 → Foundational (T002–T008): the LLM boundary is tested offline.
2. US1 (T009–T014): first real cited answer (checkpoint 4, ~1 request).
3. US2 (T015–T020): not-found and calibrated threshold (0 extra requests for off-topic).

### Incremental Delivery

4. US3 filter → US4 follow-ups (checkpoint 5) → US5 citation rejection.
5. Polish: probe answers, secret check, limitations, full quickstart run.

### Request Budget per Full Run

| Script | Model requests (no retries) |
|---|---|
| calibrate_threshold.py | 0 |
| checkpoint_4_answer.py | 2 (US1 question, US3 filtered question; France and the citation check use none) |
| checkpoint_5_conversation.py | 8 (LoRA, follow-up rewrite + answer, 5 probe questions) |

## Notes

- Verify each test fails before implementing; commit after each task.
- Never commit `.env` or a real key; `.env.example` holds placeholders only.
- Only `paperpilot/llm.py` imports `openai`.
