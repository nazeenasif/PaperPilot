---
id: 9
title: Reduce scope to twelve questions
stage: misc
date: 2026-11-13
surface: agent
model: claude-opus-5-5
feature: 005-evaluation-harness
branch: 005-evaluation-harness
user: Nazeen Asif
command: none
labels: ["evaluation", "scope", "golden-set", "future-work"]
links:
  spec: specs/005-evaluation-harness/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - evaluation/golden.py
 - evaluation/__main__.py
 - tests/evaluation/test_golden.py
 - specs/005-evaluation-harness/spec.md
 - specs/005-evaluation-harness/tasks.md
 - eval/GOLDEN_GUIDE.md
 - eval/golden.json
tests:
 - tests/evaluation/test_golden.py (28 passed)
 - full pytest: 1002 passed
---

## Prompt

I merged 004 into main on GitHub. Update local main, then merge main into 005-evaluation-harness so it has the verdicts commit. Then reduce Feature 5's scope: I'll write 12 golden questions (2 per paper plus 2 near-miss). Run only the free retrieval experiments (baseline, MiniLM reranker, TinyBERT reranker, hybrid, prefix) and generate the results table. Mark the judge, calibration and answer evaluation as future work in the spec and tasks. Update the target counts in the golden-set check, then stop and tell me where to write the 12 questions.

## Response snapshot

Local main updated to 00df7ad and merged into 005 (9391570). The golden check's targets were reduced to 10 single (2 per paper) and 2 near-miss, with other kinds optional and table answers counted only (failing tests, then 91a1891). spec.md gained a "Scope (2026-11-13)" section, FR-001/SC-001 at 12 questions, and future-work marks on US3/US4/US6, FR-005, FR-009–FR-022, FR-024a/b, FR-025–FR-025b and SC-003/005/006/007/010. tasks.md tags T032–T047 and T052–T059 [FUTURE], with Checkpoint 11 reduced to 0 requests. The guide and golden.json comments show the new targets. 0 model requests.

## Outcome

- ✅ Impact: Feature 5 is now golden set + free retrieval rows + generated table.
- 🧪 Tests: 1002 passed.
- 📁 Files: listed above.
- 🔁 Next prompts: researcher writes 12 questions (T016); then T017–T019, retrieval code T020–T031, report T048–T051.
- 🧠 Reflection: retrieval rows' answer columns read "not measured".

## Evaluation notes (flywheel)

- Failure modes observed: none.
- Graders run and results (PASS/FAIL): pytest PASS.
- Prompt variant (if applicable): none.
- Next experiment (smallest change to try): none.
