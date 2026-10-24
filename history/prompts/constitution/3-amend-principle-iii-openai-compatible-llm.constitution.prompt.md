---
id: 3
title: Amend Principle III OpenAI-Compatible LLM
stage: constitution
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: none
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: /sp.constitution
labels: ["constitution", "amendment", "principle-iii", "llm", "openrouter"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: history/adr/0003-llm-boundary-and-retry-policy.md
  pr: null
files:
 - .specify/memory/constitution.md
 - specs/002-grounded-qa-citations/plan.md
 - history/adr/0003-llm-boundary-and-retry-policy.md
tests:
 - none
---

## Prompt

Amend Principle III (MINOR): the LLM is a model reached through an OpenAI-compatible API, selected by LLM_PROVIDER, LLM_BASE_URL and LLM_MODEL, with the key in LLM_API_KEY. Free-tier models are the default; any paid model must be an explicit configuration choice. Only llm.py talks to the LLM.

## Response snapshot

Constitution 1.1.0 → 1.2.0 (MINOR, backward compatible: Gemini/Groq still usable via their
OpenAI-compatible endpoints). Principle III renamed "OpenAI-Compatible LLM, Free Tier by
Default": OpenAI-compatible API; LLM_PROVIDER/LLM_BASE_URL/LLM_MODEL + LLM_API_KEY via config;
free tier default, paid only by explicit configuration; settings-only switching; only llm.py
talks to the LLM. Technology Stack lines (LLM, Configuration, Excluded) aligned. Sync Impact
Report replaced. Feature 2 plan: Principle III row now passes, provider Complexity Tracking row
removed. ADR-0003 negative consequence updated. Templates and commands contain no provider
names.

## Outcome

- ✅ Impact: Feature 2 design fully complies with the constitution.
- 🧪 Tests: none (documentation change)
- 📁 Files: constitution.md, Feature 2 plan.md, ADR-0003
- 🔁 Next prompts: /sp.tasks for 002-grounded-qa-citations
- 🧠 Reflection: MINOR chosen as requested; it removes a restriction rather than breaking anything existing.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): version line matches report PASS; no stale provider names outside the report PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
