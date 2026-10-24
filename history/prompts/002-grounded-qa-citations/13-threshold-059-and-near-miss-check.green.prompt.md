---
id: 13
title: Threshold 0.59 and Near-Miss Check
stage: green
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: none (direct request)
labels: ["threshold", "calibration", "near-miss", "checkpoint-4", "grounding"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: history/adr/0004-grounding-and-citation-validation.md
  pr: null
files:
 - .env.example
 - paperpilot/config.py
 - tests/test_settings.py
 - specs/002-grounded-qa-citations/research.md
 - specs/002-grounded-qa-citations/data-model.md
 - specs/002-grounded-qa-citations/plan.md
 - specs/002-grounded-qa-citations/quickstart.md
 - history/adr/0004-grounding-and-citation-validation.md
 - scripts/checkpoint_4_answer.py
tests:
 - pytest: 283 passed
 - scripts/checkpoint_4_answer.py nearmiss: PASS, 3 LLM requests (budget 3)
---

## Prompt

Set RELEVANCE_THRESHOLD to 0.59 (the calibration's own suggestion) in settings defaults, .env.example and research R8, noting the rule: never reject on-topic questions; word-level rejection is best effort. Commit.

Add a "nearmiss" part to checkpoint 4 (budget 3) that asks the three topic-level near-miss questions through ask(). For each, print the answer, citations, fallback_reason, and the text of every cited passage. PASS when the answer is not-found (any fallback_reason). When the model gives a cited answer instead, print WARN and show the cited passages, so I can judge by eye whether they actually support the claims. Run it and stop.

## Response snapshot

3dce67f: default 0.59 in config.py (+ test), .env.example (with the rule as a comment), R8
(rule, calibration table, margins 0.039 below lowest on-topic and 0.002 above the highest
word-level near-miss), data-model, plan, quickstart, ADR-0004. Effective threshold 0.59 (.env
does not override). Added checkpoint 4 "nearmiss" part. Run: "How was GPT-4 trained?" →
not-found (model_not_found), 10.48 s; "How does Llama 2 handle safety tuning?" → not-found,
10.93 s; "What is the context window of Claude?" → WARN: cited answer "Claude-1.3 … 8K tokens,
Claude-1.3 (100K) … 100K tokens [1, 3]", and both cited Lost in the Middle passages state
exactly that — the papers do answer it, so the question is mislabelled as a near-miss.
3 LLM requests.

## Outcome

- ✅ Impact: calibrated threshold in place; the not-found rule caught both true topic-level near-misses.
- 🧪 Tests: 283 passed; checkpoint 4 nearmiss PASS.
- 📁 Files: see list.
- 🔁 Next prompts: replace the Claude question with a true near-miss (e.g. Claude 3) in calibration and checkpoint; US3.
- 🧠 Reflection: a "near-miss" must be checked against the papers' text, not assumed from the paper titles.

## Evaluation notes (flywheel)

- Failure modes observed: question-set labelling error; Llama reply reported reasoning tokens (416) above completion tokens (380), a provider accounting quirk.
- Graders run and results (PASS/FAIL): pytest PASS; checkpoint 4 nearmiss PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): swap in "What is the context window of Claude 3?" and rerun nearmiss (3 requests).
