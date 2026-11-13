---
id: 8
title: Write Failing Prompts Tests
stage: red
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: /sp.implement
labels: ["tdd", "red", "prompts", "citations", "us1"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: history/adr/0004-grounding-and-citation-validation.md
  pr: null
files:
 - specs/002-grounded-qa-citations/tasks.md
 - tests/test_prompts.py
tests:
 - tests/test_prompts.py: collection error (ModuleNotFoundError paperpilot.prompts) — expected red
 - rest of suite: 230 passed
---

## Prompt

In T019, require at least 2 word-level near-miss questions (like the electrical transformers one) and at least 2 topic-level ones (in-domain but unanswered by these papers, e.g. "How was GPT-4 trained?"), reported as separate groups. Commit that change.

Then /sp.implement the US1 test tasks only (T009 up to, but not including, the first implementation task). Show the failing pytest output and stop. Do not write service.py or prompts.py code yet.

## Response snapshot

T019 now requires ≥4 clear off-topic, ≥2 word-level near-miss and ≥2 topic-level near-miss
questions, reported as separate groups (committed ac8560f; added a note that topic-level
near-misses are expected to pass the threshold and be caught by the model's not-found rule).
Scope = T009 only (T010 is the first implementation task). Wrote tests/test_prompts.py:
NOT_FOUND exact; 8 required rule phrases plus NOT_FOUND and "[1]" in SYSTEM_INSTRUCTION;
passage tags numbered in order, question last, text/attribute escaping, passages cannot
close their own tag; extract_citations single/grouped/ranges/en dash/adjacent/order/non-
citations; check_citations valid/invalid split and uncited sentences incl. bullets;
word_count excluding [n]. Pytest: collection error on missing paperpilot.prompts; rest 230
pass. No prompts.py or service.py written.

## Outcome

- ✅ Impact: US1 prompt contract fixed by tests before code.
- 🧪 Tests: red as expected (missing module); 230 others pass.
- 📁 Files: tests/test_prompts.py, tasks.md
- 🔁 Next prompts: T010 implement prompts.py, then T011–T014
- 🧠 Reflection: Rule phrases in SYSTEM_INSTRUCTION are pinned by tests; wording changes will need test updates.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): failure is import-only PASS; file compiles PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
