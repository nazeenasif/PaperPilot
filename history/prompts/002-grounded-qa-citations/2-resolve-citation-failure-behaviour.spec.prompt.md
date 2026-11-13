---
id: 2
title: Resolve Citation Failure Behaviour
stage: spec
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: /sp.specify (clarification answer)
labels: ["spec", "clarification", "citations", "constitution"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/002-grounded-qa-citations/spec.md
 - specs/002-grounded-qa-citations/checklists/requirements.md
tests:
 - none
---

## Prompt

A

## Response snapshot

Applied option A: when an answer has an invalid citation or no citations, the researcher gets
the not-found sentence plus a warning listing the invalid numbers (or missing citations) and
the original answer text. Added a Clarifications section, updated User Story 5 scenario 2,
FR-009 and the Answer entity; removed both NEEDS CLARIFICATION markers. Checklist now passes
all 16 items.

## Outcome

- ✅ Impact: Spec consistent with constitution Principle V; ready for planning.
- 🧪 Tests: none (spec stage)
- 📁 Files: spec.md, checklists/requirements.md
- 🔁 Next prompts: /sp.clarify (optional) or /sp.plan
- 🧠 Reflection: The warning keeps user story 5's intent without weakening grounding.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): spec quality checklist 16/16 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
