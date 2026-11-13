---
id: 15
title: SC-008 Timeout and Filtered Questions
stage: green
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: /sp.implement
labels: ["sc-008", "timeout", "latency", "us3", "filter", "checkpoint-4"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: history/adr/0003-llm-boundary-and-retry-policy.md
  pr: null
files:
 - specs/002-grounded-qa-citations/spec.md
 - specs/002-grounded-qa-citations/research.md
 - specs/002-grounded-qa-citations/data-model.md
 - .env.example
 - paperpilot/config.py
 - paperpilot/llm.py
 - tests/test_settings.py
 - tests/test_llm.py
 - tests/test_service.py
 - scripts/checkpoint_4_answer.py
 - specs/002-grounded-qa-citations/tasks.md
tests:
 - pytest: 292 passed
 - scripts/checkpoint_4_answer.py us3: PASS, 1 LLM request
---

## Prompt

Amend SC-008: median generate time of answered questions in a checkpoint run ≤ 15 s; not-found and maximum generate times are reported, not checked. Record in research.md the free-endpoint variance (same GPT-4 question: 10.5 s vs 37.5 s), and add a planned evaluation experiment: LLM_REASONING_EFFORT low vs default, measuring both faithfulness/correct refusals and latency. Add a 60 s per-request timeout in llm.py (configurable, tested with the fake client) that raises a readable LLMError. Commit.

Then /sp.implement T021–T023 (US3 filtered questions). Tests first, commit after each task. Run checkpoint 4's US3 part, show the answer, the paper of every passage used, and the request count, then stop.

## Response snapshot

00459f9: SC-008 amended; research R13 (latency variance 10.5 s vs 37.5 s, median rule, timeout)
and R14 (reasoning-effort experiment: faithfulness, correct refusals, latency, reasoning
tokens); LLM_TIMEOUT_SECONDS (default 60, ≥1) in config, data-model, .env.example; llm.py
passes it to the client and reports persistent timeouts as "… did not answer within 60 s on
4 attempt(s) … raise LLM_TIMEOUT_SECONDS"; 7 new tests (red first); checkpoint 4 now checks
the median generate time of answered questions and reports not-found/max times. US3: T021
edda3b0 three tests passed on first run (filter already wired since T013) — strengthened the
prompt assertion to check paper titles; T022 02a3033 no code change, noted in tasks.md; T023
checkpoint 4 "us3" part. Run: "What are the two pre-training tasks of BERT?" filtered to
BERT → all 6 passages from BERT, model replied not-found (the Masked LM / NSP passages are not
in the top 6, as the probe found: ranks 13 and 25), 6.57 s, 1 request.

## Outcome

- ✅ Impact: filter verified end to end; timeout configurable; SC-008 measurable.
- 🧪 Tests: 292 passed; checkpoint 4 us3 PASS.
- 📁 Files: see list.
- 🔁 Next prompts: US4 follow-ups (T024–T028).
- 🧠 Reflection: the filtered question shows correct refusal on a retrieval miss rather than an invented answer (SC-006 behaviour).

## Evaluation notes (flywheel)

- Failure modes observed: heredoc collapsed "\n" again (fixed with Edit); weak test assertion found and tightened.
- Graders run and results (PASS/FAIL): pytest PASS; checkpoint 4 us3 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): add a filtered question whose answer is in the top 6 (e.g. BERT's pre-training data) so the US3 part also shows a cited answer.
