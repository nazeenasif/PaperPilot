---
id: 15
title: Text Average Check and Table Merging
stage: green
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 001-pdf-ingest-search
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: none (direct request)
labels: ["chunking", "tables", "checkpoint-2", "sc-003", "known-limitations"]
links:
  spec: specs/001-pdf-ingest-search/spec.md
  ticket: null
  adr: history/adr/0002-passage-identity-and-chunking.md
  pr: null
files:
 - scripts/checkpoint_2_chunk.py
 - paperpilot/ingest.py
 - tests/test_chunking.py
 - docs/known-limitations.md
 - specs/001-pdf-ingest-search/spec.md
 - specs/001-pdf-ingest-search/research.md
 - specs/001-pdf-ingest-search/tasks.md
tests:
 - unit tests (all except store/library): 150 passed
 - scripts/checkpoint_2_chunk.py papers: PASS (coverage 99.1–99.9%, text averages 162–176)
---

## Prompt

Decisions:
1. Checkpoint 2 checks: coverage ≥ 97% (all passages); average words of TEXT passages within 150–230; remove the passage-count check. Update spec SC-003 and the script.
2. Merge consecutive table-like blocks (with an adjacent caption) into one table passage up to CHUNK_WORDS, splitting evenly if longer. Failing test first: three consecutive table-row blocks plus a caption become one table passage.
3. Keep SC-003's 9-of-10 readability goal. Add to docs/known-limitations.md: blocks mixing prose with table rows or figure labels stay in text passages, and table header rows may stay with prose; current readability on samples is about 12 of 15. Add an open item to research.md: "If evaluation shows retrieval failures caused by table/figure text in prose passages, implement line-level block splitting."

Commit each separately, rerun checkpoint 2, show the summary per paper plus the table samples, and stop.

## Response snapshot

82536d6: SC-003 and checkpoint 2 now check coverage ≥ 97% and text-passage average 150–230;
count check removed; T027 updated. e8d086a: failing tests first (merge of caption + 3 rows,
even split 33→17/16; caption-between-tables guard already passed), then _units merges
consecutive table-like blocks; replaced a value-based index lookup with a flag; R8, FR-010a,
T026 updated. 5d549de: known-limitations "Tables and figures" entry and research "Open items".
Checkpoint 2 PASS on all 5: table passages fell from 53 to 31 in total (Attention 10→4,
LoRA 21→12). Table samples: LoRA and Attention merged multi-row tables; RAG table with its
caption; BERT 10-word fragment; Lost in the Middle sample is a figure axis.

## Outcome

- ✅ Impact: Checkpoint 2 passes; tables consolidated.
- 🧪 Tests: 150 unit tests pass; checkpoint 2 PASS.
- 📁 Files: checkpoint_2_chunk.py, ingest.py, test_chunking.py, known-limitations.md, spec/research/tasks.
- 🔁 Next prompts: T028–T031 (store, library, checkpoint 3).
- 🧠 Reflection: Figure axis labels still qualify as tables; harmless for search but noted.

## Evaluation notes (flywheel)

- Failure modes observed: figure axis ticks classified as table; short table fragments split from their header rows.
- Graders run and results (PASS/FAIL): unit PASS; checkpoint 2 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
