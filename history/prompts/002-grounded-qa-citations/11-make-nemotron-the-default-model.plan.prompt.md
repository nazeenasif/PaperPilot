---
id: 11
title: Make Nemotron the Default Model
stage: plan
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: none (direct request)
labels: ["llm", "model", "defaults", "openrouter"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: history/adr/0003-llm-boundary-and-retry-policy.md
  pr: null
files:
 - .env.example
 - paperpilot/config.py
 - tests/test_settings.py
 - specs/002-grounded-qa-citations/research.md
 - specs/002-grounded-qa-citations/plan.md
 - specs/002-grounded-qa-citations/data-model.md
 - specs/002-grounded-qa-citations/quickstart.md
 - history/adr/0003-llm-boundary-and-retry-policy.md
tests:
 - tests/test_settings.py: 25 passed; full suite: 268 passed
---

## Prompt

Make nvidia/nemotron-3-ultra-550b-a55b:free the documented default: update .env.example, research R12 and the plan, keeping google/gemma-4-31b-it:free noted as the alternative for a later model-comparison experiment. Commit.

## Response snapshot

The pinned-model decision lives in research R2 (R12 is rate limits), so R2 now names Nemotron
(chosen after the first real checkpoint 4 runs: correct cited answer, ~178 reasoning tokens,
3–5 s) with Gemma as the alternative, and R12 notes that a model comparison doubles requests
and needs the 1,000/day limit. Also updated the code default (config.py) and its test so docs
and code agree, plus .env.example (Gemma as a commented alternative), plan, data-model,
quickstart and ADR-0003.

## Outcome

- ✅ Impact: one consistent default model across code, docs and ADR.
- 🧪 Tests: 268 passed.
- 📁 Files: see list.
- 🔁 Next prompts: US2 (T015–T020)
- 🧠 Reflection: changing only docs would have left config.py contradicting them.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): reference grep shows no stale default PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
