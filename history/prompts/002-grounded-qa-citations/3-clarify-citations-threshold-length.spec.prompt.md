---
id: 3
title: Clarify Citations Threshold and Length
stage: spec
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: /sp.clarify
labels: ["clarify", "spec", "citations", "threshold", "answer-length"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/002-grounded-qa-citations/spec.md
tests:
 - none
---

## Prompt

/sp.clarify (no additional arguments)

Answers given during the session: Q1 "C", Q2 "A", Q3 "A".

## Response snapshot

Asked 3 questions and integrated each into spec.md (Clarifications, Session 2026-10-24):
1. Per-sentence citation checking → warning only (FR-008a, edge case, Answer and Citation
   report entities).
2. Threshold precedence → never reject on-topic questions; threshold just below the lowest
   on-topic top score; off-topic rejection best effort, rate recorded (FR-003, SC-003).
3. Answer length → ≤ ~150 words, ≤ ~300 when detail is requested (FR-004a, SC-011).
Stopped at 3; remaining gaps low impact or plan-level.

## Outcome

- ✅ Impact: Citation checking, threshold calibration and answer length are now testable.
- 🧪 Tests: none (spec stage)
- 📁 Files: specs/002-grounded-qa-citations/spec.md
- 🔁 Next prompts: /sp.plan
- 🧠 Reflection: SC-003 previously required two goals that the score distribution may make incompatible.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): 4 clarification bullets (1 from /sp.specify + 3); no NEEDS CLARIFICATION markers PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
