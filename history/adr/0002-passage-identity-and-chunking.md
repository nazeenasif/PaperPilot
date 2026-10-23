# ADR-0002: Passage Identity and Chunking Strategy

> **Scope**: Document decision clusters, not individual technology choices. Group related decisions that work together (e.g., "Frontend Stack" not separate ADRs for framework, styling, deployment).

- **Status:** Accepted
- **Date:** 2026-10-23
- **Feature:** 001-pdf-ingest-search
- **Context:** Search results must be traceable to paper, section and page; re-adding a paper
  must never duplicate data; and the later grounded-answer feature will cite passages by
  number and validate those citations against retrieved passages (Principle V). That makes
  the shape and identity of a passage a long-lived contract shared by ingest, store, library,
  prompts, service and the eval harness. Passages must also read sensibly on their own
  (SC-003) and never cross a section boundary.

## Decision

- **Paper identity**: `paper_id` = first 12 hex characters of SHA-1 of the file bytes
  (content-derived, file-name independent; used for duplicate checks, filters and delete).
- **Passage identity**: `passage_id` = `"{paper_id}-{n}"`, n = 0-based position in the paper;
  identical input and settings always produce identical IDs.
- **Sectioning**: canonical heading regex (canonical names such as "Methods", "Conclusion")
  plus numbered top-level headings labelled with their own text, guarded by a sequence
  rule (number greater than the previous numbered heading and at most 2 higher); text before the first heading is "Front Matter"; stop at References/Bibliography.
- **Chunking**: per section, pack whole paragraphs (blocks) up to `CHUNK_WORDS` (220); hard-split
  only oversized paragraphs; carry the last `CHUNK_OVERLAP` (40) words into the next passage of
  the same section only; never emit a pure-overlap passage; drop final leftovers under
  `MIN_CHUNK_WORDS` (30). All three are environment settings.
- **Passage metadata** (stored with each passage): `paper_id`, `title`, `section`, `page`
  (page of first non-overlap word), `position`, `word_count`, `source_file`, `page_count`.

## Consequences

### Positive

- Re-adding the same file (any name) is a cheap, exact duplicate check; IDs survive restarts.
- Deterministic passage IDs let later features, tests and the eval harness refer to passages
  stably and validate citations against them.
- Section-bounded, paragraph-aligned passages read naturally and carry an accurate section
  label, improving both search relevance and future citation quality.
- Every rule is a pure function (`clean`, `detect_heading`, `chunk_sections`) that is unit
  tested offline.

### Negative

- A revised version of a paper (different bytes) gets a new ID and coexists with the old one;
  the user must delete the old version manually.
- Passage IDs depend on chunking settings and heading rules: changing them changes IDs, so
  stored eval expectations or saved citations keyed by passage ID must be regenerated
  (re-ingest required).
- Regex headings miss unnumbered non-standard headings and can occasionally mistake a
  numbered line for a heading; appendices after References are excluded by design.
- Passage sizes vary (paragraph packing), so some passages are well below or above 220 words.

## Alternatives Considered

- **Alternative A — random UUIDs / file-name IDs + fixed word windows**: simplest to write,
  but duplicates on re-add (or on rename), unstable citations, and passages cut mid-sentence
  across sections.
- **Alternative B — sentence-based chunking with an NLP sentence splitter**: cleaner
  boundaries, but adds a dependency and abbreviation/equation edge cases for modest gain over
  paragraph packing.
- **Alternative C — font-size/layout-based heading detection**: catches unnumbered headings,
  but needs span-level font data and per-venue tuning; harder to explain and test.
- **Alternative D — content hash of each passage text as passage ID**: stable across
  position shifts, but long, unreadable IDs and collisions for repeated boilerplate text;
  position-based IDs are easier to read in citations and logs.

## References

- Feature Spec: specs/001-pdf-ingest-search/spec.md (FR-003, FR-004, FR-008–FR-012)
- Implementation Plan: specs/001-pdf-ingest-search/plan.md
- Related ADRs: ADR-0001 (Local Retrieval Stack)
- Evaluator Evidence: history/prompts/001-pdf-ingest-search/3-plan-pdf-ingestion-semantic-search.plan.prompt.md;
  research.md R5–R8, data-model.md
