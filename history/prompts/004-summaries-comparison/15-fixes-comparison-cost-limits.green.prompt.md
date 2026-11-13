---
id: 15
title: Fixes, comparison, cost and limits
stage: green
date: 2026-11-10
surface: agent
model: claude-opus-5-5
feature: 004-summaries-comparison
branch: 004-summaries-comparison
user: Nazeen Asif
command: /sp.implement US3 and US5
labels: ["comparison", "cost-limits", "sentence-splitting", "re-processing", "checkpoint-7"]
links:
  spec: specs/004-summaries-comparison/spec.md
  ticket: null
  adr: history/adr/0009-saved-results-and-multi-request-runs.md
  pr: null
files:
 - paperpilot/prompts.py
 - paperpilot/service.py
 - paperpilot/library.py
 - paperpilot/ingest.py
 - paperpilot/errors.py
 - api/routes.py
 - api/schemas.py
 - api/errors.py
 - api/state.py
 - scripts/checkpoint_7_summaries.py
 - frontend/app/compare/page.tsx
 - frontend/components/compare/
 - frontend/lib/useComparison.ts
 - frontend/lib/sentences.ts
 - frontend/components/summary/
 - frontend/components/states/
 - frontend/components/source/SourceViewer.tsx
 - eval/probe_notes.md
 - docs/verification/checkpoint-7-2026-11-10.md
 - specs/004-summaries-comparison/tasks.md
tests:
 - tests/test_sentences.py
 - tests/test_results_cache.py
 - tests/test_summarize_saved.py
 - tests/test_chunking.py
 - tests/test_prompts_compare.py
 - tests/test_compare.py
 - tests/test_runs.py
 - tests/api/test_comparisons_api.py
 - tests/api/test_runs_api.py
 - tests/test_checkpoint_7_compare.py
 - frontend/tests/sentences.test.ts
 - frontend/tests/source-moved.test.tsx
 - frontend/tests/compare.test.tsx
 - frontend/tests/cost-limits.test.tsx
 - frontend/e2e/smoke.spec.ts
---

## Prompt

1. Sentence splitting: don't split after common abbreviations (et al., e.g., i.e., Fig., Eq., Sec., Tab., vs., cf.) or inside decimals. Tests first, including the claims 10–12 sentence from the v4 report and a TL;DR containing "et al.". Make sure the uncited-sentence count uses the same splitter.
2. Re-processing must not delete saved summaries or comparisons: mark them earlier, with the reason "paper re-processed" (FR-017). Tests first.
3. Table tail: merge a final table piece shorter than MIN_CHUNK_WORDS into the previous piece of the same table. Tests first using LoRA Table 2. Re-process the papers; rerun geometry, facet probe and calibration (0 requests). Do not regenerate the summary.
4. Record in eval/probe_notes.md: F3 "wrong column" (claim 15, with the disproved header hypothesis), the F2 variant (Data claim 9), and claim 5's incomplete citations.
Commit each separately. Then continue with /sp.implement for US3 (comparison) and US5 (cost and limits), tests first, one commit per task. Run checkpoint 7's comparison and offline-states parts (4 planned requests) and stop.

## Response snapshot

Fixes 1–4 committed. The splitter is shared by the engine and the UI through common test cases. Re-processing now marks results earlier (reason passages_changed, shown as "Generated before this paper was re-processed"), marks citations whose passage changed as moved, and refuses part retries on an earlier result. Table tails merge: 220 passages, 100% exact highlights, threshold 0.58. A later regression from fix 2, `moved` in Ask answers, was fixed in its own commit.

US3 and US5: T015–T020, T027–T030, T033 and T045–T050, one commit per task, tests first. Comparisons share the facet table and the whole-paper gate at k=3. Runs are checked against today's requests before starting, and a systemic failure stops the run while keeping finished parts. One lock covers every model task (busy_task). The Compare screen and the cost and limit states are in place.

Checkpoint 7 (compare, not-reported, states): 4 planned, 0 retries, PASS; 10 of 10 shown cells verified; BERT Limitations not reported. Flags: claim 11 attaches SQuAD 2.0's +5.1 F1 to SWAG (F3 shape); claim 5 uncited.

Tests: pytest 921; Vitest 221; Playwright F4 12.

## Outcome

- ✅ Impact: comparisons work end to end with per-cell grounding; limits enforced before and during runs.
- 🧪 Tests: written first for every task; see the list above.
- 📁 Files: see the list above.
- 🔁 Next prompts: Polish T051–T054 (full quickstart, keyboard pass, boundary checks, known limitations); hand check of the two reports.
- 🧠 Reflection: the F3 shape recurred in a comparison cell, a number from the neighbouring paragraph, so it is not specific to tables.

## Evaluation notes (flywheel)

- Failure modes observed: wrong-item number (claim 11); an uncited sentence in a verified cell; a commit made without checking its tests (T016, amended) and a regression caught one task later (moved in answers).
- Graders run and results (PASS/FAIL): pytest PASS; vitest PASS; playwright F4 PASS; checkpoint 7 compare/not-reported/states PASS.
- Prompt variant (if applicable): SUMMARY_PROMPT_VERSION 8
- Next experiment (smallest change to try): run T054's full quickstart with all checkpoint parts.
