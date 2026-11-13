---
id: 14
title: Output limit, split tables, LoRA v4
stage: green
date: 2026-11-08
surface: agent
model: claude-opus-5-5
feature: 004-summaries-comparison
branch: 004-summaries-comparison
user: Nazeen Asif
command: follow-up to checkpoint 7 v3
labels: ["output-budget", "table-headers", "saved-results", "checkpoint-7", "faithfulness"]
links:
  spec: specs/004-summaries-comparison/spec.md
  ticket: null
  adr: history/adr/0008-per-part-grounding-and-structured-output.md
  pr: null
files:
 - paperpilot/errors.py
 - paperpilot/llm.py
 - paperpilot/ingest.py
 - paperpilot/library.py
 - paperpilot/service.py
 - scripts/checkpoint_7_summaries.py
 - frontend/components/summary/SummaryView.tsx
 - frontend/lib/types.ts
 - docs/known-limitations.md
 - docs/verification/checkpoint-7-2026-11-08-v4.md
 - eval/facet_probe.md
 - eval/threshold_calibration.md
 - history/adr/0008-per-part-grounding-and-structured-output.md
 - specs/003-web-app/spec.md
 - specs/004-summaries-comparison/spec.md
 - specs/004-summaries-comparison/plan.md
 - specs/004-summaries-comparison/research.md
 - specs/004-summaries-comparison/data-model.md
 - specs/004-summaries-comparison/contracts/web-api.md
 - specs/004-summaries-comparison/checklists/requirements.md
tests:
 - tests/test_cut_off_tokens.py
 - tests/test_llm_budget.py
 - tests/test_chunking.py
 - tests/test_summarize_saved.py
 - frontend/tests/summarize-picker.test.tsx
---

## Prompt

1. Record reasoning and visible token counts for failed (cut-off) parts too, shown in the checkpoint report.
2. Raise the output limit for summary sections, TL;DR and comparison rows to 8,192 (model maximum 65,536); answers stay at 2,048. Update ADR-0008 and R5 with the v2/v3 evidence (Results 2,607 → over 4,096).
3. Split tables: repeat the table's header row at the start of every passage of a split table. Tests first using LoRA Table 2. Re-process the papers, rerun the geometry check, facet probe and calibration (0 requests).
4. Check regeneration against US2 scenario: a regeneration with any failed part must not replace the last complete summary as current; keep the complete one available. Fix if needed, with a test.
5. Update the spec references to the deleted design images: designs live in the PaperPilot UI canvas; screenshots of the running app go in the README.
Then retry Results and the TL;DR (2 requests). Report claim 14's number, whether the TL;DR keeps the GPT-3 scope, and the token split for every part. Stop.

(Follow-up to a question: re-processing deletes the partial summary the retry needs. The researcher chose "Regenerate in full": 6 requests instead of 2.)

## Response snapshot

Five items committed; 776 pytest and 180 Vitest pass. Item 4 found a real gap: a stale complete summary could be replaced, and a kept current one lost the run's finished parts. A run with failed parts is now saved beside the complete summary and retried from there. Correction to the previous report: v2 was deleted by re-processing, not overwritten by v3.

221 passages, only LoRA Table 2 changed; 100% exact highlights; threshold 0.58; all gates ok.

Checkpoint: 6 planned, 0 retries, PASS, largest output 2,114 of 8,192. Claim 14 (now 15) is still wrong: Wq, Wv is given 91.7, and Table 5 has 91.3, even with the header in the passage. The TL;DR keeps the GPT-3 scope, but in one run with no GLUE numbers available. Results read only the caption-tail piece of Table 2. The sentence rule splits at "et al.", which makes false uncited flags.

## Outcome

- ✅ Impact: limit raised, counts kept, complete summaries protected; the header fix did not correct claim 14.
- 🧪 Tests: written first; see the list above.
- 📁 Files: see the list above.
- 🔁 Next prompts: fix the "et al." sentence split; stop a table's caption tail becoming its own passage; decide how to handle the claim 14 pattern.
- 🧠 Reflection: the header was necessary input but not sufficient; the model still paired the caption's claim with the column's highest number.

## Evaluation notes (flywheel)

- Failure modes observed: wrong column despite labels; "et al." breaks sentence checks; a split table's small tail outranks its rows in search; re-processing deletes the saved summary a planned retry needed.
- Graders run and results (PASS/FAIL): pytest PASS; vitest PASS; geometry PASS; calibration PASS; checkpoint 7 summary PASS.
- Prompt variant (if applicable): SUMMARY_PROMPT_VERSION 8
- Next experiment (smallest change to try): teach the sentence rule "et al.", then rerun the states part with 0 requests.
