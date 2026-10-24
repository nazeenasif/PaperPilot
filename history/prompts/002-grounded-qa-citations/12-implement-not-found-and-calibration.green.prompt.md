---
id: 12
title: Implement Not-Found and Calibration
stage: green
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: /sp.implement
labels: ["us2", "not-found", "threshold", "calibration", "checkpoint-4"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: history/adr/0004-grounding-and-citation-validation.md
  pr: null
files:
 - tests/test_prompts.py
 - tests/test_service.py
 - paperpilot/prompts.py
 - paperpilot/service.py
 - scripts/calibrate_threshold.py
 - eval/threshold_calibration.md
 - scripts/checkpoint_4_answer.py
 - specs/002-grounded-qa-citations/tasks.md
tests:
 - pytest: 283 passed
 - scripts/calibrate_threshold.py: PASS, 0 LLM requests
 - scripts/checkpoint_4_answer.py us2: PASS, 0 LLM requests
---

## Prompt

Then /sp.implement T015–T020 (US2 not-found and threshold calibration). Tests first, commit after each task. Run the calibration script (0 LLM requests) and checkpoint 4's US2 part. Show the score table per question group, the chosen threshold with its margin, and the request count, then stop.

## Response snapshot

T015 835f215 is_not_found tests (heredoc mangled \' and \u escapes into a syntax error; fixed
with Edit and verified via ast before committing). T016 ea95902 four service tests (red). T017
3e00d32 is_not_found (quotes, case, curly apostrophe, missing period, leading match). T018
209ab1d threshold filter + not-found with fallback_reason no_passages / below_threshold /
model_not_found; 283 pass. T019 b40a0af calibrate_threshold.py + eval/threshold_calibration.md:
on-topic 7 (0.629–0.844), clear off-topic 6 (0.449–0.544), word-level near-miss 3
(0.513–0.588), topic-level near-miss 3 (0.639–0.698); suggestion 0.59 (lowest on-topic 0.629 −
0.03); configured 0.60 kept: 0.029 below the lowest on-topic question, 0.012 above the highest
word-level near-miss, 0.056 above the highest clear off-topic; topic-level near-misses pass
as designed. T020: checkpoint 4 US2 part plus optional part arguments (us1/us2); France →
exact not-found, below_threshold, 0 LLM requests.

## Outcome

- ✅ Impact: US2 complete; off-topic questions cost no model requests.
- 🧪 Tests: 283 passed; calibration and checkpoint 4 US2 PASS with 0 requests.
- 📁 Files: see list.
- 🔁 Next prompts: US3 (T021–T023); record the calibration evidence in research R8 at T035.
- 🧠 Reflection: word-level near-misses sit within 0.012 of the threshold; the model's not-found rule must cover anything slightly above.

## Evaluation notes (flywheel)

- Failure modes observed: shell heredoc escape collapse (caught before commit).
- Graders run and results (PASS/FAIL): pytest PASS; calibration PASS; checkpoint 4 US2 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): run topic-level near-misses through the model to confirm the not-found rule catches them.
