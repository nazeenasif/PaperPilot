# ADR-0006: Citation Highlight Geometry

> **Scope**: Document decision clusters, not individual technology choices. Group related decisions that work together (e.g., "Frontend Stack" not separate ADRs for framework, styling, deployment).

- **Status:** Accepted
- **Date:** 2026-10-24
- **Feature:** 003-web-app
- **Context:** Constitution Principle IX requires that a citation opens the source PDF at the
  cited page with the retrieved passage highlighted. The viewer note says the highlighted text
  is exactly what the model read. Spec SC-002 asks for at least 90% of citations highlighted.

  Passages are not verbatim page text (ADR-0002):
  - Words hyphenated across lines are rejoined, and whitespace is normalised.
  - Blocks are reordered by column bands.
  - Each passage starts with 40 overlap words from the previous passage, often from another
    block or page.
  - Tables are flattened.

  PyMuPDF already reads block and word coordinates during parsing, but the current code throws
  them away. Papers ingested before this feature have no stored PDF. When their file is
  re-added, FR-018 (amended 2026-10-24) forbids re-embedding, but allows a separate "Mapping
  highlights" step in the attach job.

## Decision

- **Geometry at ingest:**
  - `ingest.parse_pdf` keeps each text block's word boxes (`get_text("words")`) and the size of
    each page.
  - Cleaned words are aligned back to raw words greedily. A raw word ending in `-` joined with
    the next raw word matches a rejoined word. Any other mismatch falls back to that block's
    line boxes.
  - `chunk_sections` records which blocks and word ranges, including overlap words, form each
    passage, and sets `Passage.regions`: one rectangle per line segment per page, in PDF
    points.
- **Storage:**
  - A per-paper layout file, `<LIBRARY_DIR>/pdfs/<paper_id>.layout.json`, holds the page sizes,
    the chunk settings used and `passage_id → regions`.
  - It sits next to the stored PDF copy and is written atomically. ChromaDB metadata (scalars
    only) and the store schema are unchanged.
- **Attach path (existing papers):** the attach job stores the PDF, then runs a "Mapping
  highlights" step: parse and chunk only, never embedding.
  - The layout is written only if every regenerated passage id and text equals the stored
    passages, as the same set in the same order.
  - Otherwise a mismatch marker is written instead.
- **Read path:** `library.get_passage` only reads files and never parses. With no verified
  layout it returns `layout_reason` = `no_pdf`, `mismatch` (with `can_reprocess`) or
  `unavailable`.
- **Re-process:** `library.reprocess_paper` rebuilds a paper from its stored PDF: parse, chunk,
  embed, layout. It swaps the passages in under the write lock only after embedding succeeds,
  and clears the marker. It is offered in the viewer as "Re-process paper for exact
  highlights".
- **Viewer:**
  - react-pdf renders the single cited page. A DOM overlay draws the regions, scaled from points
    to pixels.
  - Regions on the next page appear when the reader turns to it.
  - Without regions, the page is still shown, with the passage text alongside and a note
    (FR-013).

## Consequences

### Positive

- Highlights are exact and deterministic, and they cover precisely the words the model read,
  overlap included.
- The geometry is a by-product of a parse that already runs: no extra pass for new papers, and
  about 1–2 s per paper on attach.
- Everything is testable offline in Python with generated PDFs: alignment, regions, layout file,
  the match and mismatch paths, and re-process.
- Opening a citation is a cheap file read, never hidden work.
- A changed chunk setting can't produce wrong highlights. The id and text check refuses the
  layout and offers re-processing instead.

### Negative

- More ingest code: word alignment, region merging, layout files, the mismatch marker and a
  re-process job.
- Layouts are tied to the chunk settings they were built with. Changing those settings means
  re-processing papers to get exact highlights back.
- Unusual PDFs (ligature glyphs, rotated or vertical text, unusual encodings) can break word
  alignment. These fall back to line boxes or to the text-beside-page view.
- A table passage is highlighted as its whole block area, not cell by cell.
- Re-processing can change passage ids, so an answer already on screen can cite a passage that
  no longer exists. That chip needs a "passage no longer in the library" state.

## Alternatives Considered

- **Alternative A: fuzzy text matching in the viewer.**
  - Normalise the pdf.js text layer and the passage, then search with an edit-distance window.
  - No ingest change.
  - But approximate and slow on long pages. It fails on two-column order, ligatures and overlap
    words that start in another block, and it is hard to test, so SC-002 would depend on luck.
  - Rejected as both the primary method and a second fallback (Principle VIII).
- **Alternative B: block-level boxes only.**
  - Simpler: no word alignment.
  - But it over-highlights whenever a passage starts or ends mid-paragraph, which happens for
    every overlap and every split oversized paragraph, so it breaks "exactly what the model
    read".
- **Alternative C: geometry in ChromaDB metadata as a JSON string.** Mixes rendering data into
  the vector store and enlarges every query payload. The layout file keeps the store schema
  untouched.
- **Alternative D: build the layout lazily on the first citation view.**
  - The original plan.
  - Rejected on 2026-10-24: it hides work in a read request, makes the first citation slow, and
    can't be shown as progress.
- **Alternative E: re-ingest legacy papers fully on attach.** Exact, but spends embedding time,
  and FR-018 forbids re-embedding known content.

## References

- Feature Spec: specs/003-web-app/spec.md (US2 scenarios 1–7, US3 scenario 4, FR-012–FR-015,
  FR-018, FR-018a, SC-002, SC-004; clarification amendment of 2026-10-24)
- Implementation Plan: specs/003-web-app/plan.md (Key Decisions 4–5)
- Data Model: specs/003-web-app/data-model.md (layout file, highlight status, job transitions)
- Related ADRs: ADR-0002 (Passage Identity and Chunking), ADR-0005 (Web Stack and Progress
  Transport)
- Evaluator Evidence: specs/003-web-app/research.md R4, R5, R14;
  history/prompts/003-web-app/6-build-layout-at-attach-time.spec.prompt.md
