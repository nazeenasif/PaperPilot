---
id: 7
title: Generate evaluation harness tasks
stage: tasks
date: 2026-11-11
surface: agent
model: claude-opus-5-5
feature: 005-evaluation-harness
branch: 005-evaluation-harness
user: Nazeen Asif
command: /sp.tasks
labels: ["tasks", "evaluation", "tdd", "request-budget"]
links:
  spec: specs/005-evaluation-harness/spec.md
  ticket: null
  adr: history/adr/0010-evaluation-harness-architecture.md, history/adr/0011-llm-judge-and-calibration.md, history/adr/0012-retrieval-experiments-and-gate.md
  pr: null
files:
 - specs/005-evaluation-harness/tasks.md
tests:
 - none
---

## Prompt

Generate tasks for 005-evaluation-harness in this order: golden-set format and validator; retrieval metrics and the baseline row (0 requests); reranker (MiniLM-L6 and TinyBERT), hybrid and prefix rows (0 requests); the best-configuration rule; judge and calibration; answer evaluation for the baseline and the winner; report and README generation; then the optional rows. Mark human tasks explicitly: writing the golden questions (Claude Code may draft evidence phrases, I confirm each against the PDF) and filling the hand verdicts. Tests before code with the fake LLM only; one commit per task; every task that uses real requests states its planned count.

## Response snapshot

59 tasks in the order requested, after Setup and Foundational. US1 5, US2 12, US3 4, US4 8, US5 14 (best rule, report, optional rows), US6 2, plus 14 Setup, Foundational and Polish; 14 parallel. Every implementation task follows a failing-test task using the scripted LLM. Human tasks: T016 (confirm the golden set), T039 (hand verdicts), T048 and T057 (takeaways). Golden items carry `confirmed`, and the check fails on drafts. Sessions (US6) come before the first real request. Real requests are T041 (one per calibration item, at least 20), T044 (about 75), T045 (about 75, or 0), and the optional T054–T056 (75, 75 and up to 190).

## Outcome

- ✅ Impact: Feature 5 is ready for /sp.implement; Checkpoint 11 is reachable at about 125–185 requests.
- 🧪 Tests: none run (task generation).
- 📁 Files: see the list above.
- 🔁 Next prompts: /sp.analyze or /sp.implement for Setup, Foundational and US1.
- 🧠 Reflection: the five retrieval rows can satisfy the two-experiment criterion at no cost once takeaways are written.

## Evaluation notes (flywheel)

- Failure modes observed: none.
- Graders run and results (PASS/FAIL): task format check PASS (59 of 59).
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
