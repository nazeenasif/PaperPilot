---
id: 9
title: Write Failing US1 Tests
stage: red
date: 2026-10-23
surface: agent
model: claude-opus-5-5
feature: 001-pdf-ingest-search
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: /sp.implement
labels: ["tdd", "red", "tests", "us1"]
links:
  spec: specs/001-pdf-ingest-search/spec.md
  ticket: null
  adr: history/adr/0001-local-retrieval-stack.md, history/adr/0002-passage-identity-and-chunking.md
  pr: null
files:
 - tests/test_clean.py
 - tests/test_order.py
 - tests/test_headings.py
 - tests/test_sections.py
 - tests/test_title.py
 - tests/test_chunking.py
 - tests/test_store_helpers.py
 - tests/conftest.py
 - tests/test_library.py
 - specs/001-pdf-ingest-search/tasks.md
 - specs/001-pdf-ingest-search/research.md
tests:
 - pytest: 8 collection errors (ModuleNotFoundError paperpilot.ingest / paperpilot.store; ImportError store) — expected red
 - tests/test_settings.py: 14 passed
---

## Prompt

T010–T018 only: write the US1 tests and the conftest fixtures. Do NOT write any implementation code in ingest.py, store.py or library.py yet. Run pytest, show me the failing output (it should fail on missing functions, not on errors in the tests themselves), commit, and stop.

## Response snapshot

Wrote 8 test files plus conftest.py (fixtures: library_env, fake_embedder bag-of-words
vectors, make_pdf/write_pdf generating single-column PDFs). No ingest/store/library code
written. pytest: all 8 new files fail at import with ModuleNotFoundError for
paperpilot.ingest / paperpilot.store; test_settings still 14 passed; compileall clean.
Verified the PDF generator separately (title, 4 headings, ~52-word paragraphs, references
on page 2; blank PDF has no text). Found PyMuPDF 2.0 deprecates `import fitz` → switched to
`import pymupdf` and updated research.md R1 and tasks T017/T024. Fixed T012 example
"2 Background" (canonical) → "2 Model Details". Corrected a chunking test that
contradicted the agreed rule (passages may reach CHUNK_WORDS + CHUNK_OVERLAP words).
Committed one commit per task (T010–T018).

## Outcome

- ✅ Impact: US1 behaviour locked down by tests before implementation.
- 🧪 Tests: red as expected (8 import errors); settings 14 passed.
- 📁 Files: 9 test files; tasks.md, research.md updated.
- 🔁 Next prompts: /sp.implement T019–T031 (US1 implementation)
- 🧠 Reflection: Tests pin API details the implementation must honour: library calls store functions via the module (for monkeypatching), settings are loaded per call (TOP_K test), AddResult.timings has parse/embed/store keys.

## Evaluation notes (flywheel)

- Failure modes observed: PyMuPDF 2.0 `fitz` deprecation; insert_textbox needs boxes taller than ~1.5x font size.
- Graders run and results (PASS/FAIL): failures are import-only PASS; test files compile PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
