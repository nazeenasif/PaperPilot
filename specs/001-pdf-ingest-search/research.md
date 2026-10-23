# Research: PDF Ingestion and Semantic Search

**Feature**: 001-pdf-ingest-search | **Date**: 2026-10-23

Each entry: Decision / Rationale / Alternatives considered. Items marked **Amended** refine a
decision given in the `/sp.plan` input because the input as written would break a requirement.

## R1. PDF text extraction

- **Decision**: PyMuPDF (`import pymupdf`; the old `fitz` name is deprecated in PyMuPDF 2.0), `page.get_text("blocks", sort=True)`, keep only text
  blocks (block type 0).
- **Rationale**: Fast, pure-wheel install on Windows, returns block bounding boxes needed for
  column ordering and page numbers.
- **Alternatives**: pypdf (no block geometry, weaker layout); pdfplumber (slower, more code for
  the same result).

## R2. Two-column reading order — **Amended**

- **Decision**: After extraction, re-order each page's blocks in bands. Blocks wider than 60%
  of the page (title, abstract, full-width captions/figures) are **band dividers**, sorted by
  `y0`; they split the page into horizontal bands. Each narrow block goes in the band given by
  its `y0`. Within a band: left-column blocks (`x0 < page_width / 2`) top to bottom, then
  right-column blocks top to bottom, then the divider that closes the band. A single-column
  page (all blocks wide) therefore keeps plain top-to-bottom order.
- **Rationale**: PyMuPDF documents `sort=True` as ordering "from top-left to bottom-right",
  i.e. by vertical position first. On a two-column page this can interleave left- and
  right-column paragraphs at similar heights, which would violate FR-007. Building our own
  order from block positions is the approach PyMuPDF's docs suggest.
- **Verification**: Checkpoint 1 prints the first 300 characters of page 2 of a two-column test
  paper (e.g. BERT) for human review.
- **Alternatives**: rely on `sort=True` alone (risks interleaving); rely on the content-stream
  order with `sort=False` (often correct for LaTeX output but not guaranteed); full layout
  analysis (pymupdf4llm / layout models — too heavy, violates Principle VIII).
- **Known limitation**: three-column or sidebar layouts, and narrow figures inside one column,
  are not handled specially.

## R3. Short-block filter — **Amended**

- **Decision**: Drop text blocks under 25 characters **unless the block's first line matches a
  heading rule** (canonical, numbered top-level, or References/Bibliography).
- **Rationale**: Headings are frequently their own block and are short ("Abstract" = 8 chars,
  "1 Introduction" = 14 chars). Filtering them first would silently break FR-008 and FR-009.
  The filter's purpose — removing page numbers, running headers, and stray labels — is kept.
- **Alternatives**: no filter (noise in passages); filter by font size (more code, needs span
  data).

## R4. Text cleaning

- **Decision**: `clean(text)`: join `word-\nword` → `wordword` only when both sides are
  letters; replace remaining newlines with spaces; collapse runs of whitespace to one space;
  strip.
- **Rationale**: Covers FR-006 with two regexes; pure function, easy to unit-test.
- **Known limitation**: genuine hyphenated compounds split at a line end ("state-of-the-\nart")
  lose their final hyphen.

## R5. Paper ID

- **Decision**: First 12 hex chars of SHA-1 of the file bytes.
- **Rationale**: Content-derived and stable (FR-003); 48 bits makes accidental collisions
  negligible for a personal library. SHA-1 is used for identity, not security.
- **Alternatives**: full hash (unwieldy in output); file name (not stable; FR-003 forbids).

## R6. Title extraction

- **Decision**: (1) PDF metadata `title` if non-empty, longer than 3 characters, and not generic
  (case-insensitive match on "untitled", starts with "microsoft word", ends with ".dvi"/".pdf"/
  ".doc"); (2) else the largest-font text on page 1, read line by line from PyMuPDF
  (`page.get_text("dict")`). A line's size is the size of its largest span, so small-caps
  titles (alternating 17.2/13.8 pt letters, as in LoRA) count as one size. Consecutive lines
  within 0.5 pt of each other's size are joined with newlines, so `clean()` rejoins a word
  hyphenated across title lines. Non-horizontal lines (e.g. the rotated arXiv stamp), lines
  starting with "arXiv:", and candidates under 3 words or containing "@" (author lines) are
  ignored, falling back to the next-largest text; (3) else the file name stem.
- **Rationale**: Implements FR-005. All 5 test papers have empty metadata, and a text-only
  "first suitable block" rule picked a permission notice (Attention), an author line (RAG)
  and half a title (BERT) at Checkpoint 1. The title is almost always the largest text on
  page 1, which is simple to explain and needs no per-paper rules.
- **Alternatives**: more text rules (skip notices, symbols, merge blocks) — brittle and
  per-paper.
- **Known limitation**: heuristic; a large banner or logo text of 3+ words would win, and a
  title split into lines of clearly different sizes is cut to its largest part; a genuine
  hyphen at a title line end is dropped (same rule as body text).

## R7. Heading detection

- **Decision**: Applied to the **first line** of each block (a heading may share a block with
  its paragraph; if so the heading line is split off). A first line that is only a section
  number ("1", "3.", "III.") is joined with the next line first, because PDFs often put the
  number and title on separate lines.
  - Numbered-paper rule: if any heading before References carries a section number, an
    unnumbered canonical heading is ignored unless it is Abstract or Limitations (stop
    headings are unaffected). At Checkpoint 1 a "Method" table column header in LoRA
    otherwise started a bogus "Methods" section.
  - Labels: an ALL-CAPS numbered heading of 2+ words is converted to title case (small words
    such as "and", "of", "the" lowercase after the first word; each part of a hyphenated word
    capitalised). Single ALL-CAPS words are kept because they are usually acronyms ("BERT").
  - Canonical regex (one compiled, case-insensitive, anchored, optional leading number like
    `1`, `1.`, `I.`, `A`): Abstract, Introduction, Related Work, Background,
    Method/Methods/Methodology/Approach (→ "Methods"), Experiments, Results, Discussion,
    Limitations, Conclusion/Conclusions (→ "Conclusion"). Line must contain nothing else
    except optional trailing punctuation.
  - Numbered top-level rule: `^(\d{1,2})\.?\s+([A-Z][A-Za-z][^.]{0,60})$`, at most 8 words, no
    digits after the number, does not end with a period, and the number is greater than the
    previous numbered heading's number and at most 2 higher (previous = 0 at the start, so the
    first may be 1 or 2). Sub-numbers ("3.1") never match.
  - Stop rule: line equals "References" or "Bibliography" (optionally numbered) → stop
    processing the paper.
- **Rationale**: Satisfies FR-008 and the clarification. The sequence check is a cheap,
  explainable guard against table rows and numbered list items; allowing a gap of up to 2
  keeps detection going when one heading is missed (e.g. lost in a figure block or filtered
  out), instead of losing every later numbered heading.
- **Known limitation**: unnumbered non-standard headings are missed; a numbered line that fits
  the sequence can still be mistaken for a heading; appendices after References are excluded
  by design.

## R8. Chunking

- **Decision**: Per section: treat each block as a paragraph; pack whole paragraphs until the
  next would exceed `CHUNK_WORDS`; hard-split only paragraphs longer than `CHUNK_WORDS`. The
  next passage starts with the last `CHUNK_OVERLAP` words of the previous passage in the
  **same section**. A passage that would contain only overlap words is never emitted. A final
  passage under `MIN_CHUNK_WORDS` is dropped. Each passage records the page of its first new
  (non-overlap) word. Passage IDs: `"{paper_id}-{n}"`, n = 0-based order within the paper.
- **Tables**: a block is table-like when it has at least 10 tokens and more than 50% of its
  tokens are numbers or symbols (a token starting with a digit or containing no letter).
  Table-like blocks are not dropped. Consecutive table-like blocks (one block per table row is
  common) are merged into one table; each table becomes its own passage(s) with `kind = "table"`
  (prose passages have `kind = "text"`). The prose buffer is flushed before the table (with
  the same minimum-new-words rule as a section end), no overlap is carried into or out of the
  table, and the prose after it starts fresh. An adjacent "Table N:" caption block joins the
  table: the caption directly before it, otherwise the one directly after it (unless that
  caption belongs to the next table); a caption between two tables starts the second one. A
  table longer than `CHUNK_WORDS` is split into equal pieces without overlap.
- **Rationale**: Paragraph packing keeps passages readable on their own (SC-003); IDs are
  deterministic, so re-ingesting gives identical IDs. At Checkpoint 2 flattened tables made
  passages unreadable when mixed with prose; isolating them keeps prose readable while table
  numbers stay searchable and can be told apart by `kind`.
- **Alternatives**: fixed word windows (cuts mid-sentence); sentence splitting (extra rules
  for abbreviations, equations).

## R9. Embeddings

- **Decision**: sentence-transformers, `BAAI/bge-small-en-v1.5`, `normalize_embeddings=True`,
  `batch_size=32`, CPU, loaded lazily once per process (cached accessor). Queries are prefixed
  with exactly `"Represent this sentence for searching relevant passages: "`; documents get no
  prefix.
- **Rationale**: Matches Principle IV; the instruction string and the "no instruction for
  passages" rule come from the model card.
- **Note**: The model card warns absolute similarity values are not a reliable relevance
  threshold; ranking matters. SC-004's 0.45–0.8 range is treated as a sanity band, not a
  pass/fail threshold.

## R10. Vector store and score

- **Decision**: `chromadb.PersistentClient(path=LIBRARY_DIR, settings=Settings(anonymized_telemetry=False))`,
  one collection `passages` with `metadata={"hnsw:space": "cosine"}`. Score =
  `clamp(1 - distance, 0, 1)` rounded to 3 decimals.
- **Rationale**: Cosine distance on normalised vectors lies in [0, 2]; `1 - distance` is cosine
  similarity in [-1, 1]. Clamping keeps FR-015's 0–1 guarantee (negative similarity is
  irrelevant for ranking anyway). Telemetry off keeps the tool fully local.
- **Filter rule**: when no paper IDs are given, pass no `where`; otherwise
  `{"paper_id": {"$in": ids}}`. Never pass an empty `$in` list.
- **k handling**: `n_results = min(k, collection.count())`; return empty if the count is 0.

## R11. Atomic add (FR-004a)

- **Decision**: Parse, clean, chunk and embed entirely in memory; then one `upsert` of all
  passages. On any exception during the write, `delete(where={"paper_id": pid})` and re-raise
  as a friendly error. "Paper present" = at least one passage with that `paper_id`.
- **Rationale**: All failure-prone, slow work happens before the first write, so the write
  window is tiny. Cleanup on error covers recoverable failures.
- **Known limitation**: a hard crash (power loss, killed process) during the upsert itself
  could leave a partial paper that the duplicate check would then treat as present. Recovery:
  delete the paper and add it again. Documented in known-limitations.

## R12. Settings

- **Decision**: Frozen dataclass `Settings` built by `load_settings()` from environment
  variables after `python-dotenv` loads `.env`. Fields and defaults: `CHUNK_WORDS=220`,
  `CHUNK_OVERLAP=40`, `MIN_CHUNK_WORDS=30`, `TOP_K=6`, `LIBRARY_DIR=data/library`,
  `EMBED_MODEL=BAAI/bge-small-en-v1.5`. Validation raises `SettingsError` naming the variable
  and value for: non-integers, non-positive values, `CHUNK_OVERLAP >= CHUNK_WORDS`,
  `MIN_CHUNK_WORDS >= CHUNK_WORDS`. `Settings.describe()` returns a printable summary.
- **Rationale**: FR-001, FR-002; frozen prevents accidental mutation.
- **Note**: LLM settings (`LLM_PROVIDER`, `LLM_MODEL`, API key, masked in `describe()`) are
  added by the LLM feature, not this one — no LLM is used here.

## R13. Logging and timings

- **Decision**: Standard `logging`, module-level loggers. INFO logs timings for parse, embed,
  store and search; model load time logged separately the first time the model loads.
  `store.load_model()` returns the load time so checkpoint scripts can warm the model before
  any timed add or search; SC-010 and SC-011 are checked on warm timings only.
  Checkpoint scripts configure logging to stdout and print timings.

## R14. Python 3.12 on this machine — **Blocker**

- **Finding**: Installed interpreters are Python 3.14 and 3.13; 3.12 is not installed.
- **Decision**: Install Python 3.12 (e.g. `winget install Python.Python.3.12`) and create the
  venv with `py -3.12 -m venv .venv`. Required by Principle I.

## R15. The guide PDF

- **Finding**: `docs/paperpilot-guide.pdf` is not present locally, so this plan could not be
  checked against it. Decisions above come from the `/sp.plan` input and the spec. Place the
  guide in `docs/` (`*.pdf` is gitignored) before `/sp.tasks` if a cross-check is wanted.

## Open items

- If evaluation shows retrieval failures caused by table/figure text in prose passages,
  implement line-level block splitting.
