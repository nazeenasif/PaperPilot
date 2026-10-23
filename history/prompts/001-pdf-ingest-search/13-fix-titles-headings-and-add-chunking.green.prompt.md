---
id: 13
title: Fix Titles Headings and Add Chunking
stage: green
date: 2026-10-23
surface: agent
model: claude-opus-5-5
feature: 001-pdf-ingest-search
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: none (direct request)
labels: ["ingest", "titles", "headings", "chunking", "checkpoint-1", "checkpoint-2"]
links:
  spec: specs/001-pdf-ingest-search/spec.md
  ticket: null
  adr: history/adr/0002-passage-identity-and-chunking.md
  pr: null
files:
 - paperpilot/ingest.py
 - scripts/checkpoint_2_chunk.py
 - tests/test_title.py
 - tests/test_sections.py
 - tests/test_headings.py
 - docs/known-limitations.md
 - specs/001-pdf-ingest-search/spec.md
 - specs/001-pdf-ingest-search/research.md
 - specs/001-pdf-ingest-search/tasks.md
tests:
 - unit tests (all except store/library): 139 passed
 - scripts/checkpoint_1_parse.py papers: PASS; LoRA title and sections correct
 - scripts/checkpoint_2_chunk.py papers: FAIL (Attention 30 and BERT 39 passages, below 40)
---

## Prompt

Fix problems 1 and 2, record problem 3:

1. Title: treat each PDF line's font size as the size of its largest span, then group consecutive lines within 0.5 pt. Also reject any title candidate containing "@". Add a failing test first with small-caps spans alternating 17.2/13.8 pt.
2. Headings: if a paper has at least one numbered heading, ignore unnumbered canonical headings except Abstract, References, Bibliography and Limitations. Add failing tests first: an unnumbered "Method" block after "3 Our Method" is not a heading; an unnumbered "Limitations" after "6 Conclusion" is.
3. Add the three-line heading truncation to docs/known-limitations.md.
Also convert ALL-CAPS section labels to title case, with a test.

Update research R6/R7 and the spec if the rules changed. Commit each fix separately, rerun checkpoint 1 and show the output.

If checkpoint 1 passes and LoRA's title and sections look right, continue with T026–T027 (chunking and checkpoint 2), run python scripts\checkpoint_2_chunk.py papers, show the full output, and stop.

## Response snapshot

944ab00 title lines sized by largest span (merge_line), joined with newlines so clean()
rejoins "LAN-GUAGE", "@" candidates rejected; 8b52d04 numbered-paper rule (unnumbered
canonical ignored except Abstract/Limitations); 9b3a972 ALL-CAPS labels of 2+ words to
title case (single words like "BERT" kept); 86abcd9 docs/known-limitations.md with
three-line heading truncation. Spec FR-005/FR-008, research R6/R7, tasks T014/T023 updated.
Checkpoint 1 PASS with correct LoRA title and sections. T026 chunk_sections (1967b78, 20
chunking tests pass) and T027 checkpoint_2_chunk.py (89a9085). Checkpoint 2 FAIL on passage
count for Attention (30) and BERT (39); averages 171–181 pass. Diagnosis: 99–100% of body
words covered, so the 40-passage floor is too high for short papers with 220/40 settings.
Samples show flattened tables reading poorly (LoRA, BERT). Stopped for user decision.

## Outcome

- ✅ Impact: Parsing correct on all 5 papers; chunking implemented.
- 🧪 Tests: 139 unit tests pass; checkpoint 1 PASS; checkpoint 2 FAIL (criterion).
- 📁 Files: ingest.py, checkpoint_2_chunk.py, tests, docs, spec/research/tasks.
- 🔁 Next prompts: decide SC-003 passage range and whether to filter numeric table blocks; then T028–T031.
- 🧠 Reflection: The guide's 40–120 range assumes longer papers; Attention has only 4,618 body words.

## Evaluation notes (flywheel)

- Failure modes observed: SC-003 lower bound inconsistent with chunk settings for compact papers; tables extracted as number runs.
- Graders run and results (PASS/FAIL): unit PASS; checkpoint 1 PASS; checkpoint 2 FAIL
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): drop blocks whose tokens are mostly non-alphabetic.
