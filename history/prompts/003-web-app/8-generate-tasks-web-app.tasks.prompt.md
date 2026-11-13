---
id: 8
title: Generate Tasks Web App
stage: tasks
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 003-web-app
branch: 003-web-app
user: Nazeen Asif
command: /sp.tasks
labels: ["tasks", "web-app", "tdd", "engine-api-frontend", "request-budget"]
links:
  spec: specs/003-web-app/spec.md
  ticket: null
  adr: history/adr/0005-web-stack-and-progress-transport.md, history/adr/0006-citation-highlight-geometry.md, history/adr/0007-llm-request-accounting-and-long-waits.md
  pr: null
files:
 - specs/003-web-app/tasks.md
tests:
 - none (task generation); format validation: 71 tasks, all in checklist format
---

## Prompt

Generate tasks for 003-web-app. Order: engine changes first (stored PDFs, attach with layout, ingest progress, request accounting and long-wait rule in llm.py, per-paper stats, arXiv ID), then the API, then the frontend, by user story priority within each. Tests before code; one commit per task naming its files; mark parallel tasks; end each story with a runnable check. No unit or component test may call the real LLM; any checkpoint that does prints its request count.

## Response snapshot

71 tasks in layers as requested: Setup T001–T006 (Python pins, hand-scaffolded Next.js with
exact pins, theme, shadcn, test runners, pdf.js worker copy); Foundational T007–T018 (settings
and errors incl. LLMError.reason, API skeleton with background readiness/CORS/trusted
hosts/error kinds/api.log, frontend client + SSE reader, contrast test, status gate, checkpoint 6
`boundary`); Engine T019–T033 by story (US1 progress events and on_retry; US2 word geometry,
stored PDFs, attach with mapping, get_passage, reprocess, geometry checkpoint; US3 embed/ingest
progress, per-paper stats, arXiv from stored page-1 passages; US5 SQLite usage with thread and
process tests, key-endpoint refresh, pre-check, long-wait rule, scripts/usage.py); API T034–T048
by story, each ending with a checkpoint 6 part (ask 1 request, viewer 0, library 0, scope 3,
states in-process 0, usage 0); Frontend T049–T066 by story, each ending with a Playwright smoke
test against a fake backend plus its checkpoint part; Polish T067–T071 (375 px + keyboard,
reduced motion and ≤ 500 ms reveal, secrets scan of build/responses/log, known limitations, full
quickstart run). Tests precede code in every story; autouse guards block real clients and the
key endpoint; checkpoint 6 plans 4 model requests (cap 8). Per story: US1 11, US2 11, US3 9,
US4 6, US5 11; 31 [P].

## Outcome

- ✅ Impact: executable task list for Feature 3.
- 🧪 Tests: format validation passed.
- 📁 Files: specs/003-web-app/tasks.md
- 🔁 Next prompts: /sp.analyze (optional), then /sp.implement starting with Setup and Foundational.
- 🧠 Reflection: the requested layer order spreads each story over three phases; per-story checks at each layer keep stories independently verifiable.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): checklist format PASS (71/71); no story labels outside story phases PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
