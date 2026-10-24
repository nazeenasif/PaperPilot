---
id: 21
title: Planned Requests And Retry Logging
stage: refactor
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: direct request
labels: ["llm", "retries", "request-budget", "logging", "checkpoints"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: history/adr/0003-llm-boundary-and-retry-policy.md
  pr: null
files:
 - paperpilot/llm.py
 - scripts/request_budget.py
 - scripts/checkpoint_4_answer.py
 - scripts/checkpoint_5_conversation.py
 - scripts/calibrate_threshold.py
 - tests/test_llm.py
 - tests/test_request_budget.py
 - specs/002-grounded-qa-citations/spec.md
 - specs/002-grounded-qa-citations/tasks.md
 - specs/002-grounded-qa-citations/quickstart.md
 - history/adr/0003-llm-boundary-and-retry-policy.md
tests:
 - pytest: 332 passed (new tests red first)
 - scripts/checkpoint_4_answer.py us5 secrets: PASS, 0 requests (plan 0)
---

## Prompt

1. Checkpoint budgets: track planned requests (first attempts) and retries separately in llm.py. Each checkpoint FAILs if planned requests exceed its plan, reports retries, and FAILs only if total requests exceed a safety cap of 2x the plan. Prove it with fake-client tests (a run with one retry passes; an unplanned extra call fails). Update tasks.md, quickstart.md and the spec's budget wording.
2. Log every retry at WARNING with attempt number, reason (429, timeout, error in a 200 response, status code) and wait time; never the key or prompt.
No real LLM requests for this change. Commit each separately and stop.

## Response snapshot

58ab7d6: llm.RequestCounts(planned, retries, total, subtraction) and request_counts();
request_count() stays the total. scripts/request_budget.py budget_checks(label, used, plan):
planned ≤ plan, total ≤ 2 × plan, retries in the description. Checkpoints plan per part
(checkpoint 4: us1 1, us3 2, nearmiss 3, others 0 → 6; checkpoint 5: conversation 5, probe 5 →
10) and sum the plan over the parts run. Tests: counts split, failed call = 1 planned + 3
retries, one retry passes, extra call fails, retries past the cap fail, zero plan. Spec FR-018,
tasks budget section/table, quickstart. 9f96610: WARNING "LLM request attempt N of 4 failed:
<reason>; retrying in W s" with reasons rate limited (HTTP 429), timeout, connection error,
error in a 200 response (code N), HTTP <status>; provider message, key and prompt never logged;
ADR-0003 updated. No real LLM requests.

## Outcome

- ✅ Impact: a single provider retry no longer fails a checkpoint; unplanned calls still do; retries are visible.
- 🧪 Tests: 332 passed.
- 📁 Files: see list.
- 🔁 Next prompts: rerun checkpoint 4 when budget allows to confirm a clean PASS; then the API + web feature.
- 🧠 Reflection: with plans summed per selected part, running a subset of parts gets a tighter, correct budget.

## Evaluation notes (flywheel)

- Failure modes observed: Bash heredocs still mangle "\n" escapes in Python source; Edit tool used instead.
- Graders run and results (PASS/FAIL): pytest PASS; offline checkpoint parts PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
