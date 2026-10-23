---
id: 10
title: Heading Sequence Through Canonical Numbers
stage: red
date: 2026-10-23
surface: agent
model: claude-opus-5-5
feature: 001-pdf-ingest-search
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: none (direct request)
labels: ["tdd", "red", "headings", "us1"]
links:
  spec: specs/001-pdf-ingest-search/spec.md
  ticket: null
  adr: history/adr/0002-passage-identity-and-chunking.md
  pr: null
files:
 - tests/test_headings.py
tests:
 - tests/test_headings.py::test_numbered_canonical_heading_updates_previous_number (added; red until ingest.py exists)
---

## Prompt

Add a test to tests/test_headings.py: a numbered canonical heading updates the previous number. Sequence "3 Model Architecture", "4 Experiments", "5 Results", "6 Analysis" must detect all four. Make sure detect_heading's return value lets the caller update the counter for canonical headings too. Commit with the other T012 tests.

## Response snapshot

Added test_numbered_canonical_heading_updates_previous_number: starting from last_number=2,
feeds each returned heading.number back as last_number and asserts all four are detected as
("Model Architecture", numbered, 3), ("Experiments", canonical, 4), ("Results", canonical, 5),
("Analysis", numbered, 6). This requires canonical headings to return their number. Folded it
into the T012 commit via `git commit --fixup` + `git rebase --autosquash` (local branch, no
remote): 558b1f4 → eb23104; later commits re-hashed with identical content.

## Outcome

- ✅ Impact: Sequence guard can no longer break after a numbered canonical heading.
- 🧪 Tests: new test compiles; red until T019/T021 (ingest.py missing).
- 📁 Files: tests/test_headings.py
- 🔁 Next prompts: /sp.implement T019–T031
- 🧠 Reflection: Without this, "6 Analysis" after "5 Results" would be rejected if the canonical number were dropped.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): final tree diff vs. pre-rebase = only tests/test_headings.py PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
