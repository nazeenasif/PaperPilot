# Feature Specification: PDF Ingestion and Semantic Search

**Feature Branch**: `001-pdf-ingest-search`
**Created**: 2026-10-23
**Status**: Draft
**Input**: User description: "Feature 1: PDF ingestion and semantic search for PaperPilot (see
docs/paperpilot-guide.pdf, Phases 0–3). Goal: a user can add research-paper PDFs to a persistent
library and search them by meaning, with every result traceable to its paper, section and page.
No LLM is involved in this feature."

## Clarifications

### Session 2026-10-23

- Q: How are top-level headings outside the standard list labelled? → A: Standard list plus
  numbered top-level headings (e.g. "3 Model Architecture") labelled with their own text;
  standard headings keep canonical names.
- Q: What happens when adding a paper fails partway through? → A: All-or-nothing; a paper
  counts as added only when all passages are stored, and partial data from a failed add is
  removed so a retry starts fresh.
- Q: How does the researcher use this feature? → A: Programmatic functions (add, search, list,
  delete) plus one runnable checkpoint script per checkpoint; no separate command-line tool.
- Q: What speed targets apply? → A: Adding a typical paper takes under 60 s on a laptop CPU
  (after first-time model download); a search over a 5–20 paper library returns in under 2 s.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Add a paper and search it by meaning (Priority: P1)

A researcher adds a text-based research-paper PDF to their library, then asks a natural-language
question and gets back the most relevant passages. Each result shows the paper title, section,
starting page, and a similarity score, so the researcher can go straight to the source.

**Why this priority**: This is the core value of the feature: without adding and searching,
nothing else matters. It is a usable MVP on its own.

**Independent Test**: Add one known paper (e.g. "Attention Is All You Need"), search
"what dataset was used for evaluation?", and confirm the top results are about evaluation data
and carry correct title, section, page, and score.

**Acceptance Scenarios**:

1. **Given** an empty library, **When** the researcher adds a text-based research-paper PDF,
   **Then** the paper is stored with a title and a set of passages and is immediately searchable.
2. **Given** a library with at least one paper, **When** the researcher searches with a
   natural-language question, **Then** up to k passages (default 6) are returned, ordered from
   most to least similar, each showing paper title, section, starting page, and a score
   between 0 and 1.
3. **Given** a paper that contains a References section, **When** it is added, **Then** no
   passage contains text from the References section or anything after it.
4. **Given** a PDF with no extractable text (e.g. a scanned document), **When** the researcher
   tries to add it, **Then** they receive a clear error message stating the PDF has no
   extractable text, nothing is stored, and the program keeps running.

---

### User Story 2 - Re-adding a paper never duplicates data (Priority: P1)

A researcher adds a PDF they have already added (same file, possibly under a different file
name). The library stays the same: no duplicate paper and no duplicate passages.

**Why this priority**: Duplicates would pollute every search result; this protects data
integrity from the first use.

**Independent Test**: Add the same PDF twice and confirm the paper count and passage count are
unchanged after the second add.

**Acceptance Scenarios**:

1. **Given** a paper already in the library, **When** the same file is added again,
   **Then** the library still contains exactly one copy of that paper and the same number of
   passages, and the researcher is told the paper was already present.
2. **Given** a paper already in the library, **When** a byte-identical copy with a different
   file name is added, **Then** it is recognised as the same paper.

---

### User Story 3 - Library persists across restarts (Priority: P1)

A researcher closes the program and opens it again later; all previously added papers are still
present and searchable without re-adding them.

**Why this priority**: A library that disappears on restart is not a library.

**Independent Test**: Add a paper, restart the program, and run the same search; results match
the pre-restart results.

**Acceptance Scenarios**:

1. **Given** papers were added in a previous session, **When** the program is restarted,
   **Then** the same papers are listed and the same search returns the same passages and scores.

---

### User Story 4 - Search within selected papers (Priority: P2)

A researcher limits a search to one or more chosen papers so results come only from those
papers.

**Why this priority**: Valuable once the library holds several papers, but the core search works
without it.

**Independent Test**: With at least two papers in the library, search filtered to one paper and
confirm every result comes from that paper.

**Acceptance Scenarios**:

1. **Given** a library with several papers, **When** the researcher searches filtered to one
   paper, **Then** every returned passage belongs to that paper.
2. **Given** a library with several papers, **When** the researcher searches filtered to two
   papers, **Then** every returned passage belongs to one of those two papers.
3. **Given** a filter naming a paper that is not in the library, **When** the researcher
   searches, **Then** they receive no results and a clear message that the paper is unknown.

---

### User Story 5 - List and delete papers (Priority: P3)

A researcher views the papers in the library (title and number of passages for each) and can
delete a paper they no longer want.

**Why this priority**: Library housekeeping; useful but not required to get value from search.

**Independent Test**: Add two papers, list them, delete one, list again, and confirm a search
no longer returns passages from the deleted paper.

**Acceptance Scenarios**:

1. **Given** a library with papers, **When** the researcher lists the library, **Then** each
   paper appears once with its ID, title, and passage count.
2. **Given** a paper in the library, **When** the researcher deletes it, **Then** it no longer
   appears in the list and none of its passages appear in any search.
3. **Given** an ID that is not in the library, **When** the researcher tries to delete it,
   **Then** they receive a clear "not found" message and the library is unchanged.

---

### Edge Cases

- PDF has no title metadata, or the metadata title is empty or generic (e.g. "Untitled",
  "Microsoft Word - ..."): title falls back to the largest-font text on page 1, then to the
  file name.
- Page 1 has a rotated arXiv stamp in the margin printed larger than the title: the stamp is
  ignored.
- Paper has no recognised section headings: all text is labelled "Front Matter".
- Paper uses a non-standard numbered top-level heading (e.g. "4 Why Self-Attention"): it starts
  a new section labelled "Why Self-Attention".
- A numbered line that is not a heading (e.g. a table row or list item) is mistaken for a
  heading: accepted as a known limitation and documented.
- Paper has no References heading: all text is kept.
- A section is shorter than the minimum passage length (30 words): it produces no passage.
- Two-column layout: text is read column by column, not across columns.
- Words hyphenated across line breaks (e.g. "repre-\nsentation") are rejoined.
- File is not a PDF, is corrupted, or cannot be opened: clear error, nothing stored.
- Adding a paper fails partway (error or interruption): no partial paper remains in the
  library, and adding the same file again succeeds completely.
- Search on an empty library: an empty result with a clear message, not an error.
- Empty or whitespace-only search query: rejected with a clear message.
- Requested k larger than the number of available passages: all available passages are returned.
- Chunking settings are invalid (e.g. overlap ≥ passage size, non-positive values): settings
  fail to load with a clear message naming the bad value.

## Requirements *(mandatory)*

### Functional Requirements

**Settings**

- **FR-001**: The system MUST load its settings (passage size, passage overlap, minimum passage
  size, default k, library location) from environment variables, with defaults of 220 words,
  40 words, 30 words, and 6 respectively.
- **FR-002**: The system MUST be able to print the loaded settings, with any secret values
  masked, and MUST reject invalid settings with a message naming the offending value.

**Adding papers**

- **FR-003**: The system MUST assign each paper a stable ID derived from the file's content, so
  that the same file always gets the same ID regardless of file name or location.
- **FR-004**: The system MUST NOT store duplicate papers or passages when a paper with an
  existing ID is added; it MUST report that the paper is already in the library.
- **FR-004a**: Adding a paper MUST be all-or-nothing: a paper counts as present (for listing,
  searching, and the duplicate check in FR-004) only once all of its passages are stored. If
  an add fails partway, any partially stored data for that paper MUST be removed, and a later
  add of the same file MUST ingest it fully.
- **FR-005**: The system MUST determine the paper title from PDF metadata; if missing or
  unsuitable, from the largest-font text on page 1 (a line's size is its largest text;
  consecutive lines within 0.5 pt of that size joined; rotated text, text starting with
  "arXiv:", candidates under 3 words and candidates containing "@" ignored); otherwise from
  the file name.
- **FR-006**: The system MUST clean extracted text by joining words hyphenated across line
  breaks and normalising whitespace.
- **FR-007**: The system MUST read two-column pages in natural reading order (left column then
  right column).
- **FR-008**: The system MUST detect these section headings: Abstract, Introduction, Related
  Work, Background, Method / Methods / Methodology / Approach, Experiments, Results,
  Discussion, Limitations, Conclusion / Conclusions (numbered or unnumbered, case-insensitive),
  and label them with a canonical name (e.g. "Methods" for Method / Methodology / Approach).
  It MUST also detect numbered top-level headings that stand on their own line (e.g.
  "3 Model Architecture", "5. Training") and label them with their own heading text (e.g.
  "Model Architecture"); an ALL-CAPS label of two or more words is converted to title case
  (e.g. "PROBLEM STATEMENT" → "Problem Statement"), while a single ALL-CAPS word such as
  "BERT" is kept. Numbered sub-headings (e.g. "3.1 Encoder") MUST NOT start a new
  section. In a paper that numbers its sections, an unnumbered canonical word (e.g. a
  "Method" table column header) MUST NOT start a section, except Abstract and Limitations
  (References/Bibliography always end the paper). Text before the first detected heading
  MUST be labelled "Front Matter".
- **FR-009**: The system MUST exclude the References section (also "Bibliography") and
  everything after it from the stored passages.
- **FR-010**: The system MUST split each section into passages of about the configured size
  with the configured overlap; a passage MUST NOT span two sections.
- **FR-011**: The system MUST drop a final leftover passage shorter than the minimum passage
  size.
- **FR-012**: Each passage MUST record its paper ID, paper title, section name, and the page
  number on which it starts.
- **FR-013**: When a PDF yields no extractable text, the system MUST raise a clear,
  user-readable error, store nothing, and continue running.

**Searching**

- **FR-014**: Users MUST be able to search with a natural-language query and receive the top k
  most similar passages (k defaults to the configured value and can be set per search).
- **FR-015**: Each result MUST show paper title, section, starting page, passage text, and a
  similarity score between 0 and 1, where higher means more similar.
- **FR-016**: Users MUST be able to restrict a search to one or more paper IDs; results MUST
  then come only from those papers.

**Library management**

- **FR-017**: Users MUST be able to list all papers with ID, title, and passage count.
- **FR-018**: Users MUST be able to delete a paper by ID, which removes all of its passages.
- **FR-019**: The library MUST persist on local disk and be available after the program
  restarts.

**Interface and checkpoints**

- **FR-019a**: The system MUST expose add, search, list, and delete as programmatic functions;
  no command-line tool is part of this feature.
- **FR-019b**: The project MUST include one runnable checkpoint script for each of Checkpoints
  0–3 that exercises these functions and prints output a reviewer can check against the
  success criteria.

**Documentation**

- **FR-020**: The project MUST document known limitations: pattern-based heading detection
  (including occasional false headings from numbered lines and missed unnumbered non-standard
  headings), heuristic title extraction, imperfect handling of equations and tables, and no support for
  scanned (image-only) PDFs.

### Key Entities

- **Paper**: A research paper in the library. Attributes: ID (derived from file content),
  title, source file name, page count, passage count.
- **Passage**: A contiguous piece of a paper's text used for search. Attributes: passage ID,
  paper ID, paper title, section name, starting page, text, word count, position within the
  paper. Belongs to exactly one paper and exactly one section.
- **Search Result**: A passage returned for a query, together with its similarity score
  (0–1) and rank.
- **Settings**: Configurable values controlling passage size, overlap, minimum passage size,
  default k, and library location.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Settings load and print without errors on a fresh setup (Checkpoint 0).
- **SC-002**: For all 5 test papers (Attention Is All You Need, BERT, RAG, LoRA, Lost in the
  Middle), a manual review finds the correct title and sensible section labels, and zero
  passages contain reference-list text.
- **SC-003**: For each test paper, passages contain at least 97% of the paper's body words
  (text before References), the passage count is within ±25% of body words / 180, the average
  passage length is within ±15% of 200 words, and at least 9 of 10 randomly sampled passages
  read sensibly on their own.
- **SC-004**: Searching "what dataset was used for evaluation?" across the 5 test papers returns
  top results that a reviewer judges to be about evaluation data, with top scores roughly in
  the 0.45–0.8 range.
- **SC-005**: 100% of results from a paper-filtered search come from the selected paper(s).
- **SC-006**: After a restart, 100% of previously added papers are listed and the same query
  returns the same passages in the same order.
- **SC-007**: Adding the same paper twice leaves the paper count and passage count unchanged.
- **SC-008**: Adding a scanned (image-only) PDF produces a clear error message in 100% of
  attempts and never terminates the program.
- **SC-009**: The known-limitations documentation exists and covers all four listed
  limitations.
- **SC-010**: Adding a typical conference paper completes in under 60 seconds on a standard
  laptop CPU, excluding the one-time model download.
- **SC-011**: A search over a library of 5–20 papers returns results in under 2 seconds.

## Assumptions

- Single local user; no accounts, sharing, or access control.
- Papers are English-language, text-based PDFs, typically arXiv / conference format.
- Interaction for this feature is through programmatic functions (add, search, list, delete);
  there is no separate command-line tool. A UI and API are later features.
- "Word" means a whitespace-separated token; passage sizes are approximate.
- Two-column detection only needs to handle standard one- and two-column academic layouts.
- The 5 test papers are downloaded locally by the user and are never committed to the
  repository.
- Similarity scores are only comparable within one search; the 0.45–0.8 range is a guide, not
  a hard threshold.

## Out of Scope

- LLM-generated answers, summaries, or paper comparison.
- Any user interface or network API.
- OCR for scanned PDFs.
- Extraction of tables, figures, or equations as structured data.
- Non-English papers.
