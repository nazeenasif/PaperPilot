---
id: 20
title: Implement Citation Rejection And Polish
stage: green
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: /sp.implement
labels: ["us5", "citations", "polish", "secrets", "probe-answers", "quickstart"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: history/adr/0004-grounding-and-citation-validation.md
  pr: null
files:
 - tests/test_service.py
 - paperpilot/service.py
 - scripts/checkpoint_4_answer.py
 - scripts/checkpoint_5_conversation.py
 - docs/known-limitations.md
 - eval/probe_answers.md
 - specs/002-grounded-qa-citations/quickstart.md
 - specs/002-grounded-qa-citations/tasks.md
tests:
 - pytest: 317 passed
 - scripts/checkpoint_0_settings.py: PASS
 - scripts/calibrate_threshold.py: PASS, suggests 0.58 (= configured), 0 requests
 - scripts/checkpoint_4_answer.py (all parts): FAIL on request budget only (7 used, budget 6; near-miss part 4/3); every functional check PASS
 - scripts/checkpoint_5_conversation.py (all parts): PASS, 10 requests (budget 12)
---

## Prompt

T029–T035 (US5 invalid citations, then Polish). Tests first, commit after each task. The full quickstart run in T035 must execute every checkpoint part end to end, including checkpoint 4's full US3 part; keep total LLM requests within today's remaining budget and report the total. Show the final pytest summary and the checkpoint summaries, then stop.

## Response snapshot

T029 a176f85 11 failing tests for review_reply and ask() rejection. T030 2c39a57 review_reply()
(invalid → NOT_FOUND + warning naming numbers + rejected_answer, reason invalid_citations; none →
no_citations; tolerant not-found → model_not_found, never "no citations"; uncited sentences warn
only); the rejected answer keeps the citation report of the rejected text. T031 7e529f5 checkpoint 4
us5 part (offline, 0 requests). T032 ee92e3a checkpoint 5 probe part → eval/probe_answers.md;
parts conversation/probe. T033 8457979 checkpoint 4 secrets part (git grep --untracked outside
.env, describe()/repr() hide key, .env ignored; verified the search finds a planted marker).
T034 d6d1666 QA limitations. T035: full run — 317 passed; calibration unchanged at 0.58;
checkpoint 4 all parts: US1 cited [3] 5.9 s, US2 below_threshold 0 requests, US3 tasks question
false not-found (known) and data question cited [1], US5 PASS, near-misses all model_not_found,
secrets PASS, SC-008 median 7.4 s; FAIL only because one near-miss request was retried (7/6).
Checkpoint 5 PASS: LoRA answered [3, 4, 6]; follow-ups rewritten to name LoRA; probes Q1, Q3, Q5
answered, Q2/Q4 not-found (expected); median 10.8 s; 10 requests. T035 total 17 requests;
today's estimated total about 33 of 50. Quickstart and tasks budget table updated (16 per run).

## Outcome

- ✅ Impact: Feature 2 tasks complete (T001–T035); invalid citations are rejected in code.
- 🧪 Tests: 317 passed; checkpoint 5 PASS; checkpoint 4 functional checks PASS, budget FAIL (retry).
- 📁 Files: see list.
- 🔁 Next prompts: reviewer verdicts in eval/probe_answers.md (SC-006); decide whether checkpoint budgets allow retries and whether retries log at WARNING; then the API + web feature.
- 🧠 Reflection: SC results — SC-001 PASS, SC-002 PASS, SC-003 PASS (0/9 on-topic rejected), SC-004 PASS, SC-005 PASS, SC-006 pending reviewer, SC-007 PASS, SC-008 PASS (7.4 s / 10.8 s), SC-009 unit-tested, SC-010 PASS (timings on every answer), SC-011 PASS (max 86 words).

## Evaluation notes (flywheel)

- Failure modes observed: one provider retry pushed checkpoint 4 over a zero-headroom budget; retries log at INFO so the checkpoint shows no reason; uncited-sentence warnings on hedging sentences ("Based on the provided passages…", "the passages do not specify…").
- Graders run and results (PASS/FAIL): pytest PASS; calibration PASS; checkpoint 4 FAIL (budget only); checkpoint 5 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): log retries at WARNING so checkpoints show them.
