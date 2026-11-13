---
id: 16
title: Polish and full quickstart
stage: green
date: 2026-11-11
surface: agent
model: claude-opus-5-5
feature: 004-summaries-comparison
branch: 004-summaries-comparison
user: Nazeen Asif
command: /sp.implement T051-T054
labels: ["polish", "quickstart", "checkpoint-7", "faithfulness"]
links:
  spec: specs/004-summaries-comparison/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - eval/probe_notes.md
 - frontend/e2e/smoke.spec.ts
 - scripts/checkpoint_6_web.py
 - scripts/checkpoint_7_summaries.py
 - docs/known-limitations.md
 - docs/verification/checkpoint-7-2026-11-11.md
 - specs/004-summaries-comparison/quickstart.md
 - specs/004-summaries-comparison/tasks.md
tests:
 - frontend/e2e/smoke.spec.ts
 - tests/test_checkpoint_7_compare.py
---

## Prompt

Record in eval/probe_notes.md: F3's second occurrence (comparison claim 11, "+5.1 F1" from SQuAD 2.0 attached to SWAG, in prose, so F3 is not table-specific), and comparison claim 17 (RAG "limitations" cell describes broader-impact concerns; grounded but off-aspect). Commit.

Then /sp.implement the Polish phase T051–T054, including the full quickstart run. Report total model requests and stop.

## Response snapshot

Notes recorded. T051–T054 committed. Quickstart drift fixed: re-processing keeps saved results, and `retry` is left out of the default checkpoint parts so the plan is the documented 10.

Full quickstart: pytest 922 passed; typecheck clean; Vitest 221 passed; Playwright 39 passed, 3 skipped. Checkpoint 7 default parts: 10 planned, 0 retries, every check passed; provider count 0 to 10 of 50. Checkpoint 6 boundary and secrets: 31 checks passed, 0 requests.

Tokens (output / reasoning, limit 8,192). LoRA: TL;DR 1,811 / 1,691; Problem 745 / 678; Method 848 / 724; Data 1,584 / 1,438; Results 1,401 / 1,256; Limitations 893 / 830. BERT vs RAG: Method 1,460 / 1,275; Datasets 2,172 / 1,936; Results 1,277 / 1,060; Limitations 767 / 672.

Success criteria: SC-001 PASS (11/11, 13/13, 1/1 citations open). SC-002 PENDING (the researcher's hand check; 39 claims listed). SC-003 PASS for reopening in 93 ms with 0 requests; a restart was not exercised in this run. SC-004 first part PASS (BERT Limitations not reported); second part PENDING, and flagged claims already go against it. SC-005 PASS (10 of 10 planned, 10 of 20 cap). SC-006 PASS (6, then 3 + 1; 40 of 50 left). SC-007 PASS (scripted states). SC-008 PASS (component and API tests). SC-009 PASS (tests and smoke). SC-010 PASS (375 px and keyboard smoke; Vitest contrast).

Flags: Wq, Wv again given 91.7 (F3, third run); the TL;DR quotes those figures as the fine-tuning comparison; "TriviaQA not used" drops its scope; Method parts cite only at the end.

## Outcome

- ✅ Impact: Feature 4's tasks are complete; the hand check remains.
- 🧪 Tests: see the counts above.
- 📁 Files: see the list above.
- 🔁 Next prompts: the researcher's hand check (SC-002); decide on per-sentence citations in sections; F3 goes to the evaluation feature's judge.
- 🧠 Reflection: claim 14's error survived every retrieval fix, so it needs a claim-level check rather than better passages.

## Evaluation notes (flywheel)

- Failure modes observed: F3 persists with the header in the passage; citations gathered at the end of a paragraph count as uncited sentences; a hung shell command (a stray `cat`) cost one long wait.
- Graders run and results (PASS/FAIL): pytest PASS; typecheck PASS; vitest PASS; playwright PASS; checkpoint 7 PASS; checkpoint 6 boundary and secrets PASS.
- Prompt variant (if applicable): SUMMARY_PROMPT_VERSION 8
- Next experiment (smallest change to try): require a citation in every section sentence, then rerun part states with 0 requests.
