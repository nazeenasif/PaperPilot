---
id: 11
title: Implement Parsing and Checkpoint 1
stage: green
date: 2026-10-23
surface: agent
model: claude-opus-5-5
feature: 001-pdf-ingest-search
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: /sp.implement
labels: ["implement", "ingest", "parsing", "checkpoint-1"]
links:
  spec: specs/001-pdf-ingest-search/spec.md
  ticket: null
  adr: history/adr/0001-local-retrieval-stack.md, history/adr/0002-passage-identity-and-chunking.md
  pr: null
files:
 - paperpilot/ingest.py
 - scripts/checkpoint_1_parse.py
 - specs/001-pdf-ingest-search/tasks.md
tests:
 - tests/test_clean.py, test_order.py, test_headings.py, test_sections.py, test_title.py, test_settings.py: 88 passed
 - scripts/checkpoint_1_parse.py papers: FAIL (Introduction not detected in 5/5; 1–2 body sections)
---

## Prompt

T019–T025: ingest.py parsing (clean, ordering, headings, sections, title, parse_pdf) and checkpoint 1. Make the related tests pass one task at a time, commit after each. Then run python scripts\checkpoint_1_parse.py papers and show me the full output. Stop there; don't start chunking.

## Response snapshot

Downloaded the 5 test papers from arXiv into papers/ (gitignored). Implemented T019–T024 in
ingest.py (dataclasses, clean, paper_id_for, order_blocks, detect_heading, build_sections,
choose_title, parse_pdf), each committed with its tests passing (88 total). Wrote
checkpoint_1_parse.py (T025). First run printed PASS but only Abstract was detected, so the
checks were tightened (Introduction required, ≥3 body sections); rerun FAILs on all 5.
Root cause: PyMuPDF yields numbered headings as "1\nIntroduction\n" (number and title on
separate lines in one block), and detection only examines the first line. Titles: wrong
for Attention (permission notice) and RAG (author line), truncated for BERT (title spans
two blocks). Reference exclusion passes on all 5. Stopped for user decision on fixes.

## Outcome

- ✅ Impact: Parsing pipeline implemented; checkpoint 1 exposes two real defects.
- 🧪 Tests: 88 unit tests pass; checkpoint 1 FAIL.
- 📁 Files: paperpilot/ingest.py, scripts/checkpoint_1_parse.py, tasks.md
- 🔁 Next prompts: fix heading split ("number line + title line"), decide title heuristic, re-run checkpoint 1
- 🧠 Reflection: Synthetic PDFs from insert_textbox put number and title on one line, so unit tests missed the real layout; add a unit test for the two-line form.

## Evaluation notes (flywheel)

- Failure modes observed: weak checkpoint assertion initially gave a false PASS; synthetic fixture did not reflect real LaTeX heading layout.
- Graders run and results (PASS/FAIL): unit tests PASS; checkpoint 1 FAIL
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): in build_sections, join a first line that is only a section number with the next line before detect_heading.
