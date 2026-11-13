---
id: 7
title: Gap Check and LLM Boundary
stage: green
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: /sp.implement
labels: ["tasks", "gap-check", "llm", "retries", "settings", "fake-client"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: history/adr/0003-llm-boundary-and-retry-policy.md
  pr: null
files:
 - specs/002-grounded-qa-citations/spec.md
 - specs/002-grounded-qa-citations/data-model.md
 - specs/002-grounded-qa-citations/contracts/answer-api.md
 - specs/002-grounded-qa-citations/research.md
 - specs/002-grounded-qa-citations/tasks.md
 - requirements.txt
 - paperpilot/errors.py
 - paperpilot/config.py
 - paperpilot/llm.py
 - tests/test_settings.py
 - tests/fake_llm.py
 - tests/conftest.py
 - tests/test_llm.py
tests:
 - pytest: 230 passed (36 new in test_llm.py, 11 new in test_settings.py)
---

## Prompt

Before implementing, verify tasks.md covers these decisions and add or adjust tasks for any gap: (1) fallback_reason on every fallback; (2) the not-found sentence is exempt from the no-citations rule, with tolerant matching (quotes, whitespace, trailing period); (3) uncited sentences are listed in a warning, never rejected; (4) answer length is a prompt instruction only, never trimmed in code, with a soft word-count report excluding [n] markers; (5) calibration includes near-miss off-topic questions, and research.md records the threshold as calibrated for bge-small on this library. Report what was missing.

Then commit all pending Feature 2 docs, ADRs, the constitution amendment and prompt history records.

Then /sp.implement Phases 1 and 2 (T001–T008). Tests first, commit after each task. Show the pytest summary and stop.

## Response snapshot

Gap check: (1) missing → FR-016a, Answer.fallback_reason/rewrite_fallback_reason, tasks
T012/T016/T025/T029; (2) partly covered → FR-009 and T029 now state tolerant not-found replies
are exempt; (3) covered; (4) missing → FR-004a no trimming + word count excluding [n],
prompts.word_count(), Answer.word_count, T009/T012, checkpoints WARN not FAIL; (5) missing →
T019 near-miss questions, research R8 "calibrated for bge-small-en-v1.5 on this library".
Pending docs were mostly already committed by the user (13942ab, 42b5ccd); committed the rest
in 79dea77. T001 e914def pins; T002 a1fe0cf tests (12 red); T003 17dbe98 LLMError; T004
effce63 settings; T005 c2f8d21 FakeClient (real openai types, httpx2); T006 2be3610 autouse
guard blocking openai.OpenAI and llm._make_client + llm_env; T007 72a3c63 tests (red: no
module); T008 llm.py: generate, retry_wait (Retry-After, X-RateLimit-Reset ms, cap 60, 2/4/8),
ProviderError for 200-with-error, length/empty → LLMError, key scrubbing, request counter.

## Outcome

- ✅ Impact: Phases 1–2 complete; the LLM boundary is fully tested offline.
- 🧪 Tests: 230 passed; no test can create a real client.
- 📁 Files: see list.
- 🔁 Next prompts: /sp.implement Phase 3 (US1) T009–T014 — first real OpenRouter call in T014.
- 🧠 Reflection: Heredoc escaping mangled "\n" again; Edit tool used for those changes.

## Evaluation notes (flywheel)

- Failure modes observed: shell heredoc quoting broke two scripted edits (no partial writes).
- Graders run and results (PASS/FAIL): pytest PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
