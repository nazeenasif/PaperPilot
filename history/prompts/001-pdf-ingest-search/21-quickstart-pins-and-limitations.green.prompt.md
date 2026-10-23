---
id: 21
title: Quickstart Pins and Limitations
stage: green
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 001-pdf-ingest-search
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: /sp.implement
labels: ["polish", "quickstart", "requirements", "known-limitations"]
links:
  spec: specs/001-pdf-ingest-search/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/001-pdf-ingest-search/quickstart.md
 - requirements.txt
 - docs/known-limitations.md
 - specs/001-pdf-ingest-search/tasks.md
tests:
 - quickstart run on fresh LIBRARY_DIR=data/library-fresh: all commands exit 0; checkpoints 0–3 and persistence PASS
 - pytest: 183 passed in 12.96s
---

## Prompt

T045–T046: run every quickstart command on a fresh LIBRARY_DIR (fixing pip vs uv pip in quickstart.md), pin direct dependencies in requirements.txt, and complete docs/known-limitations.md. Show the final pytest summary and stop.

## Response snapshot

T045 3c3638e: quickstart now uses `uv venv` / `uv pip install` (pip alternative noted), adds a
PowerShell curl.exe download loop for the 5 papers, updates checkpoint comments and explains
fresh LIBRARY_DIR. Ran every command except `uv venv` (would recreate the existing venv) with
LIBRARY_DIR=data/library-fresh: install audited, .env copied, papers downloaded (same IDs),
checkpoints 0, 1, 2, 3 (papers) and 3 (persistence) PASS, pytest 183 passed, Python snippet
works. Timings on the fresh library: model load 3.4 s, adds 12.0–23.9 s, cold first search
0.263 s, warm search 0.077 s; whole run 300.6 s. T046: pinned pymupdf==2.0,
chromadb==1.5.9, sentence-transformers==6.2.0, python-dotenv==1.2.4, pytest==9.1.1;
known-limitations.md completed (input PDFs, reading order, titles, headings, text cleaning,
tables/figures, storage, search).

## Outcome

- ✅ Impact: All 46 tasks of Feature 1 complete; quickstart verified end to end.
- 🧪 Tests: 183 passed; all checkpoints PASS on a fresh library.
- 📁 Files: quickstart.md, requirements.txt, docs/known-limitations.md, tasks.md
- 🔁 Next prompts: feature wrap-up (merge/PR), then the evaluation or LLM-answer feature.
- 🧠 Reflection: SC-004 remains partially met by design; owned by the evaluation feature.

## Evaluation notes (flywheel)

- Failure modes observed: none new.
- Graders run and results (PASS/FAIL): quickstart PASS; pytest PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
