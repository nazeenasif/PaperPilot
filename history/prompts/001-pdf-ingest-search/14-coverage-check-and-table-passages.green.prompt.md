---
id: 14
title: Coverage Check and Table Passages
stage: green
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 001-pdf-ingest-search
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: none (direct request)
labels: ["chunking", "tables", "checkpoint-2", "sc-003"]
links:
  spec: specs/001-pdf-ingest-search/spec.md
  ticket: null
  adr: history/adr/0002-passage-identity-and-chunking.md
  pr: null
files:
 - paperpilot/ingest.py
 - scripts/checkpoint_2_chunk.py
 - tests/test_chunking.py
 - specs/001-pdf-ingest-search/spec.md
 - specs/001-pdf-ingest-search/plan.md
 - specs/001-pdf-ingest-search/research.md
 - specs/001-pdf-ingest-search/data-model.md
 - specs/001-pdf-ingest-search/tasks.md
tests:
 - unit tests (all except store/library): 147 passed
 - scripts/checkpoint_2_chunk.py papers: FAIL (coverage PASS 5/5; count FAIL 5/5; average FAIL 5/5)
---

## Prompt

Decisions:

1. Passage count: replace SC-003's 40–120 range. Checkpoint 2 now checks (a) coverage: passages contain at least 97% of each paper's body words, and (b) passage count is within ±25% of body words / 180. Keep the average-words check. Update spec SC-003 and the script.

2. Tables: do not drop table-like blocks. A block is table-like when at least 10 tokens and more than 50% of tokens are numbers or symbols. A table-like block always becomes its own passage(s): flush the current prose buffer before it, never carry overlap into or out of it, and attach an adjacent "Table N:" caption block to it. Add a passage field kind = "text" | "table", stored in metadata. Write failing tests first: table-like detection (numeric table row vs prose with a few numbers), a table between two paragraphs produces three passages with no overlap crossing it, the caption stays with the table. Update data-model.md, research R8 and the spec.

Checkpoint 2: report counts of text and table passages per paper, and sample only text passages for the readability review, plus one table passage per paper shown separately.

Commit each decision separately, rerun checkpoint 2, show the full output, and stop.

## Response snapshot

c4c6488: SC-003 replaced (≥97% coverage, count within ±25% of body words/180, average kept);
checkpoint 2 computes coverage by removing detected overlap between consecutive same-section
passages; plan scale and T027 updated. 9b4ac5f: failing tests first (8 new), then
is_table_like (≥10 tokens, >50% tokens start with a digit or contain no letter), _units
(caption before table preferred, else after), table passages kind="table" split evenly with
no overlap, prose flushed before tables with the min-new-words rule; Passage.kind default
"text"; spec FR-010a + entity, research R8, data-model kind metadata, tasks T026/T027.
Checkpoint 2: coverage 99.1–99.9% PASS; count FAIL on all 5 (39/45/47/65/48 passages incl.
5–21 table passages); average FAIL on all 5 (125–153 overall, 165–176 text-only). Text
samples more readable; remaining noise from blocks mixing prose with table/figure text and
figure axis labels classified as tables. Stopped for user decision.

## Outcome

- ✅ Impact: Tables isolated from prose; checkpoint 2 measures coverage.
- 🧪 Tests: 147 unit tests pass; checkpoint 2 FAIL (count and average).
- 📁 Files: ingest.py, checkpoint_2_chunk.py, test_chunking.py, spec/plan/research/data-model/tasks.
- 🔁 Next prompts: decide whether count/average checks apply to text passages only and how to estimate expected count.
- 🧠 Reflection: Every section end and table boundary creates a partial passage, so body/180 underestimates counts.

## Evaluation notes (flywheel)

- Failure modes observed: count estimate ignores boundaries; small figure-axis blocks qualify as tables; mixed prose+table blocks stay text.
- Graders run and results (PASS/FAIL): unit PASS; checkpoint 2 FAIL
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): apply count/average checks to text passages, expected = text body words / 180 + section count.
