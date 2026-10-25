---
id: 7
title: Generate tasks summaries comparison
stage: tasks
date: 2026-10-25
surface: agent
model: claude-opus-5-5
feature: 004-summaries-comparison
branch: 004-summaries-comparison
user: Nazeen Asif
command: /sp.tasks
labels: ["tasks", "tdd", "engine-first", "checkpoint-7"]
links:
  spec: specs/004-summaries-comparison/spec.md
  ticket: null
  adr: history/adr/0008-per-part-grounding-and-structured-output.md, history/adr/0009-saved-results-and-multi-request-runs.md
  pr: null
files:
 - specs/004-summaries-comparison/tasks.md
tests:
 - none (task planning)
---

## Prompt

/sp.tasks Generate tasks for 004-summaries-comparison. Engine first (shared citation check generalised with ask() tests unchanged, summaries, TL;DR check, comparison JSON parsing, cache), then API, then frontend, by user story within each. Tests before code, one commit per task, parallel tasks marked. Unit tests use the fake LLM only; checkpoint 7 plans 10 requests with a cap of 20 and prints its counts.

## Response snapshot

Wrote specs/004-summaries-comparison/tasks.md with 54 tasks. Layers run engine → API → frontend; within each, stories follow US1, US2, US4 (P1), then US3, US5 (P2). Every implementation task is preceded by a test task that must fail first.

| Phase | Tasks | Contents |
|---|---|---|
| Setup | T001–T002 | summary fixtures and JSON-row helpers; frontend types |
| Foundational | T003–T004 | `check_citations` and `review_reply` take `allowed`; shared `format_passages` and `number_passages`; the `ask()` tests stay unchanged (git diff check) |
| Engine | T005–T020 | US1 facets, `check_tldr` (including a test documenting the F1 gap), `summarize`; US2 results cache and invalidation, reuse/regenerate/retry; US4 per-part states; US3 row prompt, `parse_row`, `compare`; US5 plan, pre-check, stop rules |
| API | T021–T033 | summaries and comparisons endpoints, `not_saved`, `model_lock`/`busy_task`, `daily_limit.needed`; checkpoint 7 parts states, summary and reopen (with the claims file), compare and not-reported |
| Frontend | T034–T050 | four tabs and `busy_task` copy; per story, a Vitest test → implementation → Playwright test |
| Polish | T051–T054 | 375 px and keyboard e2e; checkpoint 6 boundary/secrets for the new endpoints; known limitations; full quickstart run with checkpoint 7 (plan 10, cap 20) |

Counts: US1 10, US2 9, US3 10, US4 8, US5 7; 16 tasks marked [P]. Format validated: all 54 lines have a checkbox, ID, labels and a file path. Suggested MVP: US1 + US2 + US4.

## Outcome

- ✅ Impact: Feature 4 is ready for /sp.implement.
- 🧪 Tests: none (task planning).
- 📁 Files: tasks.md.
- 🔁 Next prompts: /sp.analyze, or /sp.implement starting with T001–T004.
- 🧠 Reflection: a git-diff check on the `ask()` tests makes "generalise without changing ask()" a mechanical gate rather than a promise.

## Evaluation notes (flywheel)

- Failure modes observed: T004's file paths were only in its sub-bullets; moved into the task line.
- Graders run and results (PASS/FAIL): task format check PASS (54/54).
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
