# Implementation Plan: PDF Ingestion and Semantic Search

**Branch**: `001-pdf-ingest-search` | **Date**: 2026-10-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-pdf-ingest-search/spec.md`

## Summary

Researchers add text-based research-paper PDFs to a persistent local library and search them
by meaning; every result shows paper title, section, starting page and a 0–1 score. PDFs are
parsed with PyMuPDF in column-aware reading order, cleaned, split into sections by a regex
heading detector (canonical names plus numbered top-level headings, stopping at References),
and packed into ~220-word paragraph-aligned passages with in-section overlap. Passages are
embedded locally with `BAAI/bge-small-en-v1.5` and stored in a persistent ChromaDB collection
with cosine distance. Adds are all-or-nothing. No LLM is involved. Details in
[research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (venv) — not yet installed on this machine (see R14)
**Primary Dependencies**: pymupdf, sentence-transformers (pulls in torch, CPU), chromadb,
python-dotenv; exact versions pinned in `requirements.txt` after install
**Storage**: ChromaDB `PersistentClient` at `LIBRARY_DIR` (default `data/library`, gitignored)
**Testing**: pytest (unit tests, offline); checkpoint scripts 0–3 for end-to-end checks
**Target Platform**: Windows 10/11, PowerShell, local CPU
**Project Type**: single Python package + scripts
**Performance Goals**: add a typical paper < 60 s on a laptop CPU excluding first model
download (SC-010); search over 5–20 papers < 2 s (SC-011)
**Constraints**: fully local and offline after the one-time model download; no LLM; no
LangChain; telemetry disabled
**Scale/Scope**: personal library of tens of papers, ~25–50 passages each (about one per 180 body words) (a few thousand
vectors)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Plain, typed Python | Python 3.12, no LangChain, type hints + docstrings on public functions | ✅ (3.12 must be installed first) |
| II. Modular package, single LLM boundary (v1.1.0) | `config`, `errors`, `ingest`, `store`, `library` used as defined; `prompts`, `llm`, `service` arrive in later features; no LLM calls anywhere | ✅ |
| III. Swappable free-tier LLM | not applicable (no LLM in this feature) | ✅ N/A |
| IV. Local embeddings, persistent store | bge-small-en-v1.5 locally; ChromaDB PersistentClient; re-runs never re-embed | ✅ |
| V. Grounded answers | no answers generated; retrieval keeps title/section/page per passage, which later citations need | ✅ N/A (enables) |
| VI. Secrets and data hygiene | `.gitignore` adds `.env`, `*.pdf`, `papers/`, `data/`, `.venv/`; `.env.example` committed; no secrets used | ✅ |
| VII. Testable checkpoints, measured quality | checkpoint scripts 0–3; pytest for clean/headings/chunking/settings; retrieval quality checked by Checkpoint 3 (no answer eval harness yet) | ⚠ justified below |
| VIII. Simplicity, small commits | regex + heuristics, one collection, no extra abstractions; one commit per task | ✅ |

**Post-design re-check (after Phase 1)**: unchanged. Data model uses one collection and
frozen dataclasses; contracts expose four functions; no new violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-pdf-ingest-search/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── library-api.md   # Phase 1 output (Python API contract)
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/sp.tasks — not created here)
```

### Source Code (repository root)

```text
paperpilot/
├── __init__.py
├── config.py            # Settings dataclass, load_settings(), SettingsError
├── errors.py            # PaperPilotError and subclasses
├── ingest.py            # parse_pdf, column ordering, clean, title, headings, chunking
├── store.py             # lazy embedding model, ChromaDB collection, upsert/query/delete
└── library.py           # public add_paper / search / list_papers / delete_paper

scripts/
├── checkpoint_0_settings.py
├── checkpoint_1_parse.py
├── checkpoint_2_chunk.py
└── checkpoint_3_search.py

tests/
├── test_clean.py
├── test_headings.py     # canonical, numbered, sequence guard, table-row false positives, stop
├── test_chunking.py     # budget, overlap within section only, no pure-overlap, min drop, ids, pages
├── test_settings.py     # defaults, env override, each validation error names the value
└── test_order.py        # column-aware block ordering on synthetic boxes

docs/
└── known-limitations.md

.env.example
.gitignore
requirements.txt         # exact pins
pyproject.toml           # pytest config only (testpaths, pythonpath)
```

**Structure Decision**: single package `paperpilot/` at repo root with `scripts/` and `tests/`.
`errors.py` gives `config`, `ingest`, `store` and `library` one shared error hierarchy without
importing each other (Principle II, constitution v1.1.0). `ingest.py` stays one module (parse + clean + headings
+ chunk) as requested; its pure functions are unit-tested without PyMuPDF objects.

## Key Decisions (summary; rationale in research.md)

ADRs: [ADR-0001 Local Retrieval Stack](../../history/adr/0001-local-retrieval-stack.md) (1, 2, 6–8),
[ADR-0002 Passage Identity and Chunking](../../history/adr/0002-passage-identity-and-chunking.md) (3–5).

1. PyMuPDF blocks, text blocks only, then **band-based column ordering** (wide blocks split
   the page into bands; left then right column within each band) (R2, amended).
2. Short-block filter (< 25 chars) **exempts heading lines** (R3, amended).
3. Paper ID = SHA-1(file bytes)[:12] (R5).
4. Headings: canonical regex + numbered top-level rule with a sequence guard (greater than previous, at most +2); stop at
   References/Bibliography (R7).
5. Paragraph-packing chunker with in-section overlap; IDs `{paper_id}-{n}` (R8).
6. bge-small, normalised, batch 32, lazy; query-only instruction prefix (R9).
7. Chroma cosine collection; score = clamp(1 − distance, 0, 1); no `where` when unfiltered (R10).
8. Embed-everything-then-single-upsert, cleanup on write error (R11).
9. Frozen `Settings` from `.env` with named validation errors (R12).

## Risks

1. **Heading heuristics on real papers** — numbered rule could mislabel or miss sections.
   Mitigation: sequence guard, unit tests with table-row cases, Checkpoint 1 human review on
   all 5 papers, documented limitation.
2. **torch install size/time on Windows** — sentence-transformers pulls ~200 MB+ of torch.
   Mitigation: install CPU wheel; documented in quickstart.
3. **Score band (SC-004)** — bge scores cluster high; 0.45–0.8 may not hold exactly.
   Mitigation: treat band as a sanity check, judge relevance by ranking (R9).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| No eval harness run although the feature affects retrieval | The eval harness scores answers (groundedness, citations, "not found"), which do not exist until the LLM feature | Checkpoint 3 is the interim retrieval-quality check (fixed query, filter, persistence); the eval harness arrives with the answer feature and will include retrieval queries |
