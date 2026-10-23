---
id: 3
title: Plan PDF Ingestion Semantic Search
stage: plan
date: 2026-10-23
surface: agent
model: claude-opus-5-5
feature: 001-pdf-ingest-search
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: /sp.plan
labels: ["plan", "pymupdf", "chromadb", "bge", "chunking"]
links:
  spec: specs/001-pdf-ingest-search/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/001-pdf-ingest-search/plan.md
 - specs/001-pdf-ingest-search/research.md
 - specs/001-pdf-ingest-search/data-model.md
 - specs/001-pdf-ingest-search/contracts/library-api.md
 - specs/001-pdf-ingest-search/quickstart.md
tests:
 - none
---

## Prompt

/sp.plan Plan Feature 1 (001-pdf-ingest-search) following docs/paperpilot-guide.pdf Phases 0–3. Environment: Windows, PowerShell, Python 3.12, venv.

Technical decisions:
- PDF parsing: PyMuPDF (import fitz), page.get_text("blocks", sort=True), keep only text blocks (type 0), drop blocks under 25 characters.
- Paper ID: first 12 hex chars of SHA-1 of the file bytes.
- Headings: one compiled regex for the canonical list plus a separate rule for numbered top-level headings exactly as specified in FR-008. Stop at References/Bibliography.
- Chunking: pack whole paragraphs up to the word budget, hard-split only oversized paragraphs, carry an overlap tail within a section only, never emit a pure-overlap chunk, drop leftovers under the minimum. Deterministic passage IDs "{paper_id}-{n}".
- Embeddings: sentence-transformers with BAAI/bge-small-en-v1.5, normalize_embeddings=True, batch_size=32, lazy-loaded once per process. Prepend the BGE query instruction to queries only, never to documents.
- Vector store: chromadb.PersistentClient with a collection using hnsw:space=cosine; metadata per passage: paper_id, title, section, page; score = 1 - distance. Pass no where-filter when no paper IDs are given (never an empty $in list).
- Atomic add (FR-004a): parse, chunk and embed everything in memory before writing; write with a single upsert; on any write error delete all passages for that paper_id and re-raise. Document the hard-crash case as a known limitation.
- Settings: frozen dataclass loaded from .env via python-dotenv, with validation (positive values, overlap < passage size, min size < passage size) that names the bad value.
- Logging: standard logging module; record timings for parse, embed, store and search, and the model load time separately.

Structure:
- paperpilot/: config.py, ingest.py (parse + clean + headings + chunk), store.py (embedding + ChromaDB), library.py (public add/search/list/delete functions with friendly errors).
- scripts/: checkpoint_0_settings.py through checkpoint_3_search.py, each printing PASS/FAIL for automatable checks, printing samples for human review, and printing timings.
- tests/: pytest unit tests for clean(), heading detection (canonical, numbered, false-positive cases like table rows), chunking rules, settings validation. No network or model needed for unit tests.
- docs/known-limitations.md covering everything listed in FR-020 plus revised paper versions and the hard-crash case.

Dependencies: pymupdf, chromadb, sentence-transformers, python-dotenv, pytest. Pin exact versions after install.

Suggest which decisions deserve an ADR.

## Response snapshot

Wrote plan.md, research.md (R1–R15), data-model.md, contracts/library-api.md, quickstart.md.
Verified against docs: PyMuPDF sort=True orders top-left to bottom-right (risk of column
interleaving) and BGE query instruction / no passage prefix. Amendments: column-aware block
ordering (R2); short-block filter exempts heading lines (R3); score clamped to [0,1] (R10);
added errors.py; numbered-heading "+1 sequence" guard. Constitution check: library.py and
errors.py outside Principle II module list and no eval harness run, all justified in
Complexity Tracking. Blockers: Python 3.12 not installed (3.13/3.14 only); guide PDF absent.
Agent context script added only a BOM to CLAUDE.md; reverted. Suggested ADRs.

## Outcome

- ✅ Impact: Phase 0 and 1 design artifacts complete; ready for /sp.tasks.
- 🧪 Tests: none (plan stage); unit test files planned.
- 📁 Files: plan.md, research.md, data-model.md, contracts/library-api.md, quickstart.md
- 🔁 Next prompts: /sp.adr for suggested decisions; install Python 3.12; /sp.tasks
- 🧠 Reflection: Two input decisions (sort=True, 25-char filter) would have broken FR-007/FR-008; caught by checking docs and heading lengths.

## Evaluation notes (flywheel)

- Failure modes observed: update-agent-context.ps1 found no update markers in CLAUDE.md and only added a BOM.
- Graders run and results (PASS/FAIL): constitution gate PASS with 3 justified deviations
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): add agent-context markers to CLAUDE.md if tech context there is wanted.
