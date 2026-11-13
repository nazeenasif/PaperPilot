---
id: 3
title: Prioritise experiments and keep a reserve
stage: spec
date: 2026-11-11
surface: agent
model: claude-opus-5-5
feature: 005-evaluation-harness
branch: 005-evaluation-harness
user: Nazeen Asif
command: follow-up to /sp.specify
labels: ["evaluation", "request-budget", "experiments", "priorities"]
links:
  spec: specs/005-evaluation-harness/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/005-evaluation-harness/spec.md
tests:
 - none
---

## Prompt

Prioritise: retrieval experiments first (0 requests); answer evaluation only for the baseline and the best retrieval configuration; reasoning effort and the second model are optional rows run only if budget allows. Each session uses a configurable slice of the daily quota, keeping a reserve (default 10) for normal use.

## Response snapshot

FR-024a sets the order and makes reasoning effort and the second model optional. FR-024b defines the best retrieval configuration: the highest hit@6, ties broken by MRR, only if it beats the baseline, and the developer may override it. FR-018 and SC-007 add the configurable slice and the reserve of 10. The scope-rule experiment stays in scope, after the two answer runs, recorded as an assumption for the researcher to confirm. About 225 required requests if a retrieval experiment wins, about 150 if the baseline does.

## Outcome

- ✅ Impact: the required spend is about a quarter lower and comes after the free measurements.
- 🧪 Tests: none (specification).
- 📁 Files: see the list above.
- 🔁 Next prompts: /sp.plan.
- 🧠 Reflection: "best" needed a stated rule, or the choice of what to spend on would be made after seeing the numbers.

## Evaluation notes (flywheel)

- Failure modes observed: none.
- Graders run and results (PASS/FAIL): specification checklist 16 of 16.
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
