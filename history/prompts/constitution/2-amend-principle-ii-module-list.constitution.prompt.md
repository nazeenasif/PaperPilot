---
id: 2
title: Amend Principle II Module List
stage: constitution
date: 2026-10-23
surface: agent
model: claude-opus-5-5
feature: none
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: /sp.constitution
labels: ["constitution", "amendment", "modules", "principle-ii"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - .specify/memory/constitution.md
 - specs/001-pdf-ingest-search/plan.md
tests:
 - none
---

## Prompt

Amend Principle II (MINOR): the package modules are config, errors, ingest, store, library, prompts, llm, service. library holds paper-library operations; service orchestrates answers and calls library. Only llm talks to the LLM.

## Response snapshot

Bumped constitution 1.0.0 → 1.1.0. Principle II now lists config, errors, ingest, store,
library, prompts, llm, service, with errors = shared exception hierarchy, library =
paper-library operations, service = answer orchestration that calls library; LLM boundary
unchanged. Replaced the Sync Impact Report. Propagated to Feature 1 plan.md: Principle II
row now passes and the library/errors rows were removed from Complexity Tracking (eval
harness deviation remains). Templates needed no change.

## Outcome

- ✅ Impact: Feature 1 module layout now complies with the constitution without exceptions.
- 🧪 Tests: none (documentation change)
- 📁 Files: .specify/memory/constitution.md, specs/001-pdf-ingest-search/plan.md
- 🔁 Next prompts: /sp.adr local-retrieval-stack, /sp.adr passage-identity-and-chunking, /sp.tasks
- 🧠 Reflection: MINOR is correct: guidance expanded, nothing removed or redefined.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): version line matches report PASS; no placeholder tokens PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
