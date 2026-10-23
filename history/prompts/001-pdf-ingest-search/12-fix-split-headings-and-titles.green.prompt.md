---
id: 12
title: Fix Split Headings and Titles
stage: green
date: 2026-10-23
surface: agent
model: claude-opus-5-5
feature: 001-pdf-ingest-search
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: none (direct request)
labels: ["ingest", "headings", "titles", "checkpoint-1"]
links:
  spec: specs/001-pdf-ingest-search/spec.md
  ticket: null
  adr: history/adr/0002-passage-identity-and-chunking.md
  pr: null
files:
 - paperpilot/ingest.py
 - scripts/checkpoint_1_parse.py
 - tests/test_headings.py
 - tests/test_sections.py
 - tests/test_title.py
 - specs/001-pdf-ingest-search/spec.md
 - specs/001-pdf-ingest-search/research.md
 - specs/001-pdf-ingest-search/tasks.md
tests:
 - ingest + settings unit tests: 106 passed
 - scripts/checkpoint_1_parse.py papers: PASS (all automated checks, 5/5 papers)
---

## Prompt

Go ahead with both fixes.

Headings: join a first line that is only a section number ("1", "3.", "III.") with the next line before heading detection. Write failing tests first: "1\nIntroduction\n<paragraph>" in one block is detected and split; "3\nModel Architecture" is detected as numbered; "3.1\nEncoder and Decoder Stacks" is still rejected as a sub-heading. Apply the same join in the checkpoint script helper.

Titles: use Option A. When metadata has no suitable title, take the largest-font text on page 1, joining consecutive lines within 0.5 pt of that size. Ignore non-horizontal spans, spans starting with "arXiv:", and candidate text under 3 words. Fall back to the file stem if nothing qualifies. Write failing tests first using synthetic span data (size, text, direction), including a rotated arXiv stamp larger than the title.

Update spec FR-005, research R6 and tasks T014/T023 to the new rule. Commit each fix separately, rerun python scripts\checkpoint_1_parse.py papers, show the full output, and stop.

## Response snapshot

Heading fix (146dba3): failing tests first, then heading_candidate(text) joins a number-only
first line ("1", "3.", "3.1", "III.", "A.") with the next line; used by build_sections and the
checkpoint helper; R7 note added. One new test had a data error (heading 3 with no prior
heading is correctly rejected by the sequence guard) and was fixed by adding heading 2.
Title fix (e920588): failing tests with Span(size, text, direction) first, then Span,
page_spans(page) and the largest-font choose_title; spec FR-005 + edge case, research R6,
tasks T014/T023 updated. Checkpoint 1 now PASSes on all 5 papers; 4/5 titles correct and
sections look right. Remaining issues found and diagnosed, not fixed: LoRA title (small-caps
title alternates 17.22/13.77 pt spans, so no run reaches 3 words and the author block wins);
LoRA spurious "Methods" from a table column header "Method"; Lost in the Middle heading
truncated where the heading wraps to a second line.

## Outcome

- ✅ Impact: Section detection works on real LaTeX papers; titles correct for 4/5.
- 🧪 Tests: 106 unit tests pass; checkpoint 1 PASS.
- 📁 Files: ingest.py, checkpoint_1_parse.py, 3 test files, spec/research/tasks.
- 🔁 Next prompts: decide on LoRA title (line-level size), table-header and wrapped-heading cases; then T026 chunking.
- 🧠 Reflection: Real PDFs keep surprising synthetic fixtures; checkpoint review by eye caught what automated checks did not.

## Evaluation notes (flywheel)

- Failure modes observed: small-caps titles split into alternating span sizes; canonical words used as table column headers; two-line headings.
- Graders run and results (PASS/FAIL): unit tests PASS; checkpoint 1 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): treat a PDF line's size as its largest span size when building title candidates.
