---
id: 18
title: Threshold As Top-Score Gate
stage: refactor
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: threshold semantics fix
labels: ["threshold", "calibration", "faithfulness", "us2"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: history/adr/0004-grounding-and-citation-validation.md
  pr: null
files:
 - tests/test_service.py
 - paperpilot/service.py
 - history/adr/0004-grounding-and-citation-validation.md
 - specs/002-grounded-qa-citations/research.md
 - specs/002-grounded-qa-citations/spec.md
 - specs/002-grounded-qa-citations/plan.md
 - specs/002-grounded-qa-citations/data-model.md
 - specs/002-grounded-qa-citations/quickstart.md
 - scripts/calibrate_threshold.py
 - eval/threshold_calibration.md
 - paperpilot/config.py
 - tests/test_settings.py
 - .env.example
 - eval/probe_notes.md
tests:
 - pytest: 306 passed (new gate test red first, then green)
 - scripts/calibrate_threshold.py: PASS, 0 LLM requests
 - checkpoint 5 first question only: answered, 1 LLM request
---

## Prompt

Fix the threshold semantics: RELEVANCE_THRESHOLD is a gate on the top passage's score (what the calibration measured). If the top score is below it, return not-found with fallback_reason below_threshold and no LLM call; otherwise send all top-k passages unfiltered. Tests first: a question whose top score passes but whose other passages are below the threshold still sends all k passages. Update ADR-0004, research R8 (record why: calibrated as a gate, applied as a filter, causing false not-found on short questions like "What is LoRA?") and the spec.

Add "What is LoRA?" to the calibration's on-topic group, rerun calibration (0 requests), and apply the rule (lowest on-topic minus 0.03, rounded down) even if it lowers the threshold. Then rerun only checkpoint 5's first question (1 request) and show the answer.

Add to eval/probe_notes.md a "Faithfulness cases" section with the Wq/Wv example: a correct fact attributed to passage [2], which doesn't contain it; citation validation passed it. Commit each change separately and stop.

## Response snapshot

70da2f1 test (red: 1 of 4 passages sent) replacing the per-passage filter test, plus a
just-below-gate test. cfc008b ask() gates on max score, sends all k. f9c972d ADR-0004, R8 (why),
spec FR-002/scenario/FR-016a/entity, plan, data model. 0238b47 "What is LoRA?" on-topic (0.618) →
rule gives 0.58; applied in config, tests, .env.example, quickstart, specs; on-topic 0/9
rejected, clear off-topic 6/6, word-level near-miss 2/3 (transformers 0.588 now reaches the
model). Rerun "What is LoRA?": answered with [2, 3, 4, 6], 6 passages 0.574–0.618, 1 request,
generate 8.8 s. 06f5c6a probe notes Faithfulness cases: F1 Wq/Wv (fact is in passage [1],
cited to [2]), F2 "matches or exceeds" over-generalised across [2, 4, 6].

## Outcome

- ✅ Impact: false not-found on "What is LoRA?" fixed; threshold means what it measured.
- 🧪 Tests: 306 passed; calibration PASS; 1 LLM request.
- 📁 Files: see list.
- 🔁 Next prompts: US5 (T029–T031); consider a definition-passage retrieval experiment.
- 🧠 Reflection: the Wq/Wv fact was in a provided passage ([1]) — a misattribution, not invention.

## Evaluation notes (flywheel)

- Failure modes observed: misattributed citation (F1); merged-claim over-generalisation (F2); the abstract/definition passage is not in the top 6 for "What is LoRA?" (front matter chunk has only title/authors).
- Graders run and results (PASS/FAIL): pytest PASS; calibration PASS; manual claim check F1/F2 recorded
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): title/section prefix before embedding (probe experiment 3).
