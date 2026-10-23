---
id: 5
title: Generate Tasks PDF Ingest Search
stage: tasks
date: 2026-10-23
surface: agent
model: claude-opus-5-5
feature: 001-pdf-ingest-search
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: /sp.tasks
labels: ["tasks", "tdd", "mvp", "checkpoints"]
links:
  spec: specs/001-pdf-ingest-search/spec.md
  ticket: null
  adr: history/adr/0001-local-retrieval-stack.md, history/adr/0002-passage-identity-and-chunking.md
  pr: null
files:
 - specs/001-pdf-ingest-search/tasks.md
tests:
 - none
---

## Prompt

Generate tasks for 001-pdf-ingest-search. Order by user story priority so the P1 stories form a working MVP first. Put unit tests before the code they test. Each task should be small enough for one commit and name the files it touches. Mark tasks that can run in parallel. End each user story with the checkpoint script that verifies it. Include a final task to pin requirements.txt and update docs/known-limitations.md.

## Response snapshot

Wrote tasks.md with 46 tasks in 8 phases: Setup (T001–T005, incl. installing Python 3.12),
Foundational (T006–T009, Checkpoint 0), US1 (T010–T031: 9 test tasks then implementation,
Checkpoints 1–3), US2 (T032–T034), US3 (T035–T037), US4 (T038–T040), US5 (T041–T044), Polish
(T045 quickstart run, T046 pin requirements + known-limitations). Tests precede code in every
story; library tests run offline via tmp LIBRARY_DIR, fake embedder and generated PDFs. 15
tasks marked [P]. Added pure helpers to make logic testable: order_blocks, build_sections,
choose_title, distance_to_score, build_where, store.reset_cache.

## Outcome

- ✅ Impact: Executable, TDD-ordered task list; MVP = US1–US3.
- 🧪 Tests: none run (tasks stage); 9 test files planned.
- 📁 Files: specs/001-pdf-ingest-search/tasks.md
- 🔁 Next prompts: /sp.analyze (optional), then /sp.implement starting at T001
- 🧠 Reflection: US2–US5 share library.py, test_library.py and checkpoint_3_search.py, so they are ordered rather than parallel.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): format check 46/46 tasks match checklist pattern PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
