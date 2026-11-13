---
id: 12
title: Facet gate, shared table, LoRA regeneration
stage: green
date: 2026-11-05
surface: agent
model: claude-opus-5-5
feature: 004-summaries-comparison
branch: 004-summaries-comparison
user: Nazeen Asif
command: follow-up to the section-aware retrieval
labels: ["retrieval", "relevance-gate", "facet-table", "checkpoint-7", "faithfulness"]
links:
  spec: specs/004-summaries-comparison/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - paperpilot/prompts.py
 - paperpilot/service.py
 - scripts/probe_facets.py
 - scripts/checkpoint_7_summaries.py
 - eval/facet_probe.md
 - docs/verification/checkpoint-7-2026-11-05-v2.md
 - specs/004-summaries-comparison/research.md
 - specs/004-summaries-comparison/tasks.md
 - specs/004-summaries-comparison/contracts/engine-api.md
tests:
 - tests/test_facet_retrieval.py
 - tests/test_summarize.py
 - tests/test_checkpoint_7_claims.py
---

## Prompt

Decisions:
1. Facet gating: the gate uses the top score of a whole-paper search (with Related Work and Front Matter excluded); passages are then read from the facet's preferred sections. Record in research.md: the gate answers "does this paper cover the facet?", the restriction answers "where to read it"; a wrong pass fails safe (the model reports not-found). Tests first, including LoRA-like data where the restricted score is below the gate but the whole-paper score is above.
2. Limitations: when its named sections give fewer than 2 passages, top up from the whole-paper search so every section reads 4 passages, matching the spec.
3. One shared facet table (query, preferred sections, exclusions) used by summaries now and comparison later; add a task note so comparison aspects use it.
Rerun the facet probe (0 requests) and show the Problem and Limitations rows with their gate results. Commit each separately.

Then regenerate the LoRA summary (6 planned requests), list every claim with its passage like last time, write docs/verification/checkpoint-7-<date>-v2.md, and stop.

## Response snapshot

Gate, top-up and shared table done in three commits, tests first. All 25 facet gates pass; LoRA Problem passes at 0.642 and reads 0.573 from its Introduction. Limitations reads 4 passages on all five papers. The table refactor left the probe output byte-identical. The research note says the fail-safe rests on an instruction to the model, not on code. Problem still reads only its preferred sections, so a paper with fewer than 4 passages there reads fewer.

Checkpoint: 6 planned, 0 retries, all 6 parts verified, largest output 2,782 of 4,096 tokens. 18 claims written to the v2 report. The date passed midnight during the run, so the report carries 2026-11-05.

Checked against the PDF: claim 14 gives Wq, Wv the 91.7 that belongs to the all-weights column (the passage lost the table header; the first run had the same error); claim 1 repeats F2 for DeBERTa; claim 17 has no citation, which section validation allows. Recorded as flags, verdicts left for the hand check.

Tests: pytest 715 before the checkpoint naming commit, whose 2 tests passed on their own.

## Outcome

- ✅ Impact: LoRA's Problem section now states the paper's problem; Method no longer cuts off.
- 🧪 Tests: tests/test_facet_retrieval.py extended first; tests/test_checkpoint_7_claims.py new.
- 📁 Files: see the list above.
- 🔁 Next prompts: per-sentence citation rule for sections; passages that lose a table header; whether to record the DeBERTa case as F2.
- 🧠 Reflection: a number check passes when a value appears in the passage, even when it belongs to another column.

## Evaluation notes (flywheel)

- Failure modes observed: chunking separated a table from its header and the model assigned a value to the wrong column; a section sentence without a citation passed; F2 from combining sections.
- Graders run and results (PASS/FAIL): pytest PASS; facet probe gates 25 of 25 PASS; checkpoint 7 summary PASS.
- Prompt variant (if applicable): SUMMARY_PROMPT_VERSION 6
- Next experiment (smallest change to try): require a citation in every section sentence, then rerun the states part with 0 requests.
