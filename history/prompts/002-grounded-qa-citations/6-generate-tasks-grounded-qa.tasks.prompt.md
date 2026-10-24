---
id: 6
title: Generate Tasks Grounded QA
stage: tasks
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: /sp.tasks
labels: ["tasks", "tdd", "fake-llm", "request-budget"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: history/adr/0003-llm-boundary-and-retry-policy.md, history/adr/0004-grounding-and-citation-validation.md
  pr: null
files:
 - specs/002-grounded-qa-citations/tasks.md
tests:
 - none (tasks stage)
---

## Prompt

Generate tasks for 002-grounded-qa-citations. Order by user story priority, unit tests before code, one commit per task naming the files it touches, mark parallel tasks, end each story with its checkpoint script. Include an early task to add openai to requirements.txt and pin tenacity. Unit tests must never call the real API: use a fake LLM client covering normal answers, 429 with headers, HTTP 200 with an error body, finish_reason "length", and missing usage fields. Only checkpoint scripts call OpenRouter, and they must stay well within 50 requests per day — print the number of LLM calls each checkpoint makes.

## Response snapshot

Wrote tasks.md: 35 tasks. Setup T001 (pin openai==3.37.0, tenacity==9.1.4). Foundational
T002–T008 (settings, LLMError, tests/fake_llm.py scripted client with ok/no_usage/length/
error_body/rate_limited/status_error/timeout built on httpx2 as openai 3.37.0 uses, autouse
fixture blocking real clients, llm tests then llm.py with request counter). US1 T009–T014,
US2 T015–T020 (incl. calibrate_threshold.py), US3 T021–T023, US4 T024–T028 (checkpoint 5),
US5 T029–T031 (pure review_reply), Polish T032–T035 (probe answers, secret check, limitations,
quickstart run). Budgets: checkpoint 4 ≤ 6 requests, checkpoint 5 ≤ 12, calibration 0;
~10 requests per full run. 9 tasks marked [P].

## Outcome

- ✅ Impact: Executable, TDD-ordered task list with an explicit request budget.
- 🧪 Tests: none run (tasks stage).
- 📁 Files: specs/002-grounded-qa-citations/tasks.md
- 🔁 Next prompts: /sp.implement starting at T001
- 🧠 Reflection: openai 3.37.0 uses httpx2, so fake HTTP errors must be built with httpx2 objects.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): format check 35/35 tasks match the checklist pattern PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
