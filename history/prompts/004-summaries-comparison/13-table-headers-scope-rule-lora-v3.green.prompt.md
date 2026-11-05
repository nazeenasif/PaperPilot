---
id: 13
title: Table headers, scope rule, LoRA v3
stage: green
date: 2026-11-05
surface: agent
model: claude-opus-5-5
feature: 004-summaries-comparison
branch: 004-summaries-comparison
user: Nazeen Asif
command: follow-up to checkpoint 7 v2
labels: ["chunking", "table-headers", "scope-rule", "uncited-sentences", "checkpoint-7"]
links:
  spec: specs/004-summaries-comparison/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - paperpilot/ingest.py
 - paperpilot/prompts.py
 - paperpilot/service.py
 - frontend/components/summary/CitedText.tsx
 - frontend/components/summary/SectionCard.tsx
 - docs/known-limitations.md
 - docs/design/library.png (deleted)
 - docs/verification/checkpoint-7-2026-11-05-v3.md
 - eval/facet_probe.md
 - eval/probe_notes.md
 - eval/threshold_calibration.md
 - specs/004-summaries-comparison/research.md
 - specs/004-summaries-comparison/tasks.md
tests:
 - tests/test_chunking.py
 - tests/test_prompts_summary.py
 - tests/test_facet_retrieval.py
 - tests/test_summarize.py
 - frontend/tests/summary.test.tsx
---

## Prompt

Fixes, each with failing tests first and its own commit:
1. Table header rows: when a short non-numeric block (a header row: mostly short tokens, no sentence punctuation) sits directly before a table-like block in the same column, attach it to the table passage. Tests from real cases: LoRA Table 5 (Weight Type / Wq … Wq,Wk,Wv,Wo) and Attention's "N dmodel dff h dk dv …" header. Re-chunking changes passage text, so re-process the five papers (no embedding change needed only if passage text is unchanged; otherwise re-embed), confirm 223 passages (or report the new count), rerun the geometry check and the facet probe, and recalibrate the threshold (0 requests). Remove the header-row item from docs/known-limitations.md if fixed.
2. Scope rule for summaries and comparison: add to the TL;DR, section and cell instructions: "Keep every claim's scope exactly as its source passage states it (models, datasets, conditions); never extend a result to models or tasks the passage does not name." Bump SUMMARY_PROMPT_VERSION. Record in research.md as a hypothesis from F2 (4 occurrences, 3 while combining sources), to be measured in the evaluation feature.
3. Top-up: any section-restricted facet tops up to 4 passages from the whole-paper search.
4. Confirm the summary UI flags uncited sentences as Ask does.
5. Delete the three old PNGs in docs/design/; the README will use screenshots of the running app.
Then regenerate the LoRA summary (6 requests), write the v3 report, and tell me specifically: claim 14's number, and whether the TL;DR keeps the GPT-3 scope. Stop.

## Response snapshot

Five fixes committed. Five papers re-embedded: 223 -> 221 passages, 100% exact highlights, threshold 0.58 unchanged. A split table still has its header only in its first piece, so the limitation was rewritten rather than removed. Cell instructions do not exist yet, so T016 carries a note. The summary UI did not flag uncited sentences; it does now. The notes record all 4 F2 cases as combining sources, against the request's 3 of 4, so research.md says 4 and the difference was raised. The library also holds a sixth paper, a slide deck; it was left alone and changes no calibration result.

Checkpoint: 6 planned, 0 retries, result FAIL. Results was cut off at 4,096 tokens, so neither question can be answered from this run: there is no claim 14 and the TL;DR, built without Results, makes no performance claim. The Table 5 passage does now carry its header row. No extra request was spent.

Tests: pytest 749; Vitest 179.

## Outcome

- ✅ Impact: fixes in place; their effect on the two named claims is unmeasured.
- 🧪 Tests: written first; see the list above.
- 📁 Files: see the list above.
- 🔁 Next prompts: retry Results and the TL;DR (2 requests); record tokens on failed parts.
- 🧠 Reflection: the 4,096 limit passed one real run and failed the next, so one passing run did not establish it.

## Evaluation notes (flywheel)

- Failure modes observed: Results cut off at 4,096 tokens, cause unmeasured because failed parts keep no token counts; claim 6 uncited; TL;DR claim 2 merges dataset and model pairs.
- Graders run and results (PASS/FAIL): pytest PASS; vitest PASS; geometry PASS; calibration PASS; checkpoint 7 summary FAIL.
- Prompt variant (if applicable): SUMMARY_PROMPT_VERSION 8
- Next experiment (smallest change to try): retry Results and the TL;DR, then read claim 14 and the TL;DR's scope.
