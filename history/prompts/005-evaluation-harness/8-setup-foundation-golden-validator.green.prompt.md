---
id: 8
title: Setup, foundation and golden validator
stage: green
date: 2026-11-11
surface: agent
model: claude-opus-5-5
feature: 005-evaluation-harness
branch: 005-evaluation-harness
user: Nazeen Asif
command: /sp.implement T001-T015
labels: ["evaluation", "golden-set", "engine-seams", "tdd"]
links:
  spec: specs/005-evaluation-harness/spec.md
  ticket: null
  adr: history/adr/0010-evaluation-harness-architecture.md
  pr: null
files:
 - requirements.txt
 - .env.example
 - evaluation/__init__.py
 - evaluation/__main__.py
 - evaluation/store.py
 - evaluation/experiments.py
 - evaluation/golden.py
 - eval/experiments.json
 - eval/golden.json
 - eval/GOLDEN_GUIDE.md
 - paperpilot/config.py
 - paperpilot/llm.py
 - paperpilot/service.py
 - specs/005-evaluation-harness/tasks.md
 - specs/005-evaluation-harness/spec.md
 - specs/005-evaluation-harness/data-model.md
 - specs/005-evaluation-harness/research.md
tests:
 - tests/test_config_eval.py
 - tests/test_llm_model_arg.py
 - tests/test_ask_retrieve.py
 - tests/evaluation/test_eval_store.py
 - tests/evaluation/test_experiments.py
 - tests/evaluation/test_golden.py
---

## Prompt

Change T016: I write the golden questions myself, not you. Create an empty golden-set file with the format, a commented example, and a short guide listing the question kinds and my target counts (20 single-paper with at least 1 table answer per paper, 5 cross-paper, 4 near-miss, 3 off-topic, 4 follow-ups). After I add questions, a separate task drafts evidence phrases and pages for the answerable ones; I confirm each. Update tasks.md and commit.

Then /sp.implement Setup, the foundation and US1 up to the empty golden-set file and validator. Tests first, one commit per task. Stop and tell me where to write the questions.

## Response snapshot

tasks.md rewritten for US1: T015 creates the empty file and guide, T016 (HUMAN) writes the questions, T017 drafts evidence, T018 (HUMAN) confirms it, and T019 runs the check; later tasks renumbered (61 in all). FR-001 takes the researcher's target counts; data-model.md gains `table` and `confirmed`; research R1 allows `//` comments. T001–T015 are implemented, each test task before its code, one commit per task. Engine seams: five settings, `llm.generate(model=...)` with task kind `judge`, and `ask(retrieve=...)`, each defaulting to today's behaviour. Also the evaluation cache, experiments and the configuration record, and the golden set and its check. The empty set fails the check as it should, with 0 requests. Full pytest: 999 passed.

## Outcome

- ✅ Impact: the harness foundation and the validator are ready; the golden questions are the researcher's next step.
- 🧪 Tests: 999 passed (pytest).
- 📁 Files: see the list above.
- 🔁 Next prompts: the researcher writes questions in `eval/golden.json` (T016); then T017 drafts evidence.
- 🧠 Reflection: pytest's rootdir import mode needs unique test file names across folders without `__init__.py`.

## Evaluation notes (flywheel)

- Failure modes observed: `tests/evaluation/test_store.py` clashed with `tests/test_store.py`, so it was renamed to `test_eval_store.py`; a fixture paragraph under the 30-word minimum was dropped, taking its arXiv stamp with it; a stray `cat >` waited on input twice and was stopped.
- Graders run and results (PASS/FAIL): pytest PASS (999); `python -m evaluation check` FAIL on the empty set, as expected.
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
