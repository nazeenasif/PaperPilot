# Data Model: PDF Ingestion and Semantic Search

**Feature**: 001-pdf-ingest-search | **Date**: 2026-10-23

All in-memory types are frozen dataclasses. The only persistent store is one ChromaDB
collection, `passages`, under `LIBRARY_DIR`. There is no separate papers table: paper-level
fields are repeated on each passage and aggregated when listing (a library holds tens of
papers, so this stays simple and fast).

## Settings (`config.py`)

| Field | Env var | Type | Default | Validation |
|---|---|---|---|---|
| chunk_words | `CHUNK_WORDS` | int | 220 | > 0 |
| chunk_overlap | `CHUNK_OVERLAP` | int | 40 | ≥ 0 and < chunk_words |
| min_chunk_words | `MIN_CHUNK_WORDS` | int | 30 | > 0 and < chunk_words |
| top_k | `TOP_K` | int | 6 | > 0 |
| library_dir | `LIBRARY_DIR` | Path | `data/library` | — |
| embed_model | `EMBED_MODEL` | str | `BAAI/bge-small-en-v1.5` | non-empty |

Invalid values raise `SettingsError("CHUNK_OVERLAP=300 must be less than CHUNK_WORDS=220")`.

## Block (`ingest.py`, internal)

| Field | Type | Notes |
|---|---|---|
| text | str | cleaned block text |
| page | int | 1-based page number |

## Section (`ingest.py`, internal)

| Field | Type | Notes |
|---|---|---|
| name | str | canonical name, numbered heading text, or "Front Matter" |
| blocks | list[Block] | paragraphs in reading order |

## ParsedPaper (`ingest.py`)

| Field | Type | Notes |
|---|---|---|
| paper_id | str | 12 hex chars, SHA-1 of file bytes |
| title | str | metadata → page-1 text → file stem |
| source_file | str | file name only (no directory) |
| page_count | int | |
| sections | list[Section] | References and after excluded |

## Passage (`ingest.py` → stored by `store.py`)

| Field | Type | Stored as | Notes |
|---|---|---|---|
| passage_id | str | Chroma `id` | `"{paper_id}-{n}"`, n = 0-based order in paper |
| text | str | Chroma `document` | |
| paper_id | str | metadata | used for filters, duplicate check, delete |
| title | str | metadata | |
| section | str | metadata | |
| page | int | metadata | page of first non-overlap word |
| position | int | metadata | n |
| word_count | int | metadata | |
| kind | str | metadata | `"text"` (prose) or `"table"` (table-like block and its caption) |
| source_file | str | metadata | for listing |
| page_count | int | metadata | for listing |

Embedding: 384-float vector (bge-small), normalised, stored by Chroma alongside the passage.

## PaperSummary (`library.py`, returned by `list_papers`)

| Field | Type | Notes |
|---|---|---|
| paper_id | str | |
| title | str | |
| source_file | str | |
| page_count | int | |
| passage_count | int | number of stored passages |

## SearchResult (`library.py`, returned by `search`)

| Field | Type | Notes |
|---|---|---|
| rank | int | 1-based |
| score | float | clamp(1 − cosine distance, 0, 1), 3 decimals |
| passage_id, paper_id, title, section, page, text | | from the stored passage |

## AddResult (`library.py`, returned by `add_paper`)

| Field | Type | Notes |
|---|---|---|
| paper_id | str | |
| title | str | |
| passage_count | int | |
| already_present | bool | True → nothing written (FR-004) |
| timings | dict[str, float] | seconds for parse, embed, store |

## Relationships and rules

- Paper 1 — N Passage (by `paper_id`). Each passage belongs to exactly one section.
- **Paper lifecycle**: absent → present (all passages written in one upsert) → absent (delete
  removes all passages). There is no visible "partial" state: a failed write is cleaned up
  before the error is raised (FR-004a).
- Uniqueness: `paper_id` identifies a paper; `passage_id` is unique and deterministic.
