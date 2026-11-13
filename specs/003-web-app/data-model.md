# Data Model: PaperPilot Web App (Feature 3)

The engine stays the source of truth (spec FR-001). New persistent data lives under the
gitignored `LIBRARY_DIR` (default `data/library`); nothing new is committed.

## Persistent storage

```text
data/library/
├── chroma.sqlite3 …              # Feature 1 vector store (unchanged schema)
├── pdfs/
│   ├── <paper_id>.pdf            # NEW: copy of the added PDF (FR-015)
│   └── <paper_id>.layout.json    # NEW: passage geometry (research R4)
└── usage.sqlite3                 # NEW: daily request usage (research R7)
```

### Layout file (`<paper_id>.layout.json`)

| Field | Type | Notes |
|---|---|---|
| version | int | `1`; bumped if the format changes |
| paper_id | str | equals the file name |
| chunking | {words, overlap, min_words} | settings used; a mismatch with current settings makes the file stale |
| pages | list[{number, width, height}] | PDF points, 1-based page numbers |
| passages | map passage_id → list[Region] | in reading order; may span two pages |

**Region**: `{page: int, x0, y0, x1, y1: float}` in PDF points, origin top-left (PyMuPDF
convention), one rectangle per line segment covered by the passage's words.

Validation: every passage id in the library for this paper has an entry; x0 < x1, y0 < y1, all
within the page box. Written atomically (temp file + rename), only after the id/text check
passes — at ingest (always passes: same run) or in an attach job's "Mapping highlights" step.
Missing → viewer fallback; missing because the attach check failed → fallback plus the
"Re-process paper for exact highlights" offer.

### Highlight status (per paper, derived)

| Value | Meaning |
|---|---|
| `exact` | PDF and verified layout file present |
| `mismatch` | PDF present; attach-time check failed (marker file `<paper_id>.layout-mismatch`, removed by re-processing) |
| `no_pdf` | no stored PDF |

### Usage database (`usage.sqlite3`)

Table `daily_usage`:

| Column | Type | Notes |
|---|---|---|
| day | TEXT PK | UTC date `YYYY-MM-DD` |
| used | INTEGER | requests counted (first attempts + retries), or the provider's `used` |
| request_limit | INTEGER | `DAILY_REQUEST_LIMIT` or the provider's `limit` |
| source | TEXT | `local` or `provider` |
| updated_at | TEXT | ISO-8601 UTC |

WAL mode, `busy_timeout` 5000 ms, increments inside `BEGIN IMMEDIATE`. Reset is implicit: a new
UTC day is a new row. `resets_at` = next 00:00 UTC.

## Engine entities (Python)

| Entity | Fields (new in bold) | Defined in |
|---|---|---|
| Block | text, page, **bbox, words** (word boxes) | ingest |
| ParsedPaper | paper_id, title, source_file, page_count, sections, **page_sizes**, **arxiv_id** | ingest |
| Passage | …, kind, **regions: tuple[Region, ...]** (not stored in ChromaDB) | ingest |
| AddResult | paper_id, title, passage_count, already_present, timings, **outcome** (`added`, `already_present`, `pdf_attached`, `reprocessed`), **highlights** (`exact`, `mismatch`, `no_pdf`) | library |
| PaperSummary | paper_id, title, source_file, page_count, passage_count, **text_passages, table_passages, section_count, arxiv_id, has_pdf, highlights** | library |
| PassageView | **passage_id, paper_id, title, section, page, page_count, text, kind, layout: PassageLayout \| None, layout_reason** (`no_pdf`, `mismatch`, `unavailable`), **can_reprocess** | library |
| PassageLayout | **pages (sizes), regions** | library |
| IngestProgress | **phase** (`parsing`, `chunking`, `embedding`, `mapping`, `ready`), **percent** | library (callback payload) |
| AskEvent | **kind** (`rewriting`, `searching`, `reading`, `generating`, `retry_wait`, `checking`), **detail** dict | service (callback payload) |
| RetryNotice | **attempt, max_attempts, wait_seconds, reason** | llm (callback payload) |
| RequestCounts | planned, retries, total (Feature 2) | llm |
| Usage | **used, limit, remaining, resets_at, source** | llm |
| DailyLimitError | **used, limit, resets_at** (subclass of LLMError) | errors |
| RateLimitedError | **until, daily** (subclass of LLMError) | errors |
| PdfMissingError | **paper_id** (subclass of PaperPilotError) | errors |

`arxiv_id` comes from the first page's `arXiv:NNNN.NNNNN[vN]` stamp; for existing papers it is
read from the stored page-1 passages (the stamp is in the "Front Matter" passage), so no
re-parse is needed. `section_count`, `text_passages` and `table_passages` are computed from the
stored passage metadata (`section`, `kind`).

## API-side entities (in memory, `api/`)

### UploadJob

| Field | Type | Notes |
|---|---|---|
| job_id | str | uuid4 hex |
| kind | enum | `upload` or `reprocess` |
| file_name | str | original name, or the paper title for `reprocess` (display only; never used as a path) |
| phase | enum | `queued`, `parsing`, `chunking`, `embedding`, `mapping`, `ready`, `failed` |
| percent | int \| null | 0–100 during `embedding` |
| outcome | enum \| null | `added`, `already_present`, `pdf_attached`, `reprocessed`, `failed` |
| highlights | enum \| null | `exact` or `mismatch` once known (for `pdf_attached`, the result of the mapping check) |
| paper_id | str \| null | set when known |
| error | {kind: "upload_invalid", reason} \| null | reasons: `not_pdf`, `too_large`, `no_text`, `unreadable`, `password`, `storage` |
| created_at | datetime | jobs older than 1 hour and finished are dropped |

State transitions:

- new paper: `queued → parsing → chunking → embedding → ready` (outcome `added`, highlights
  `exact`);
- known content, PDF stored: `queued → ready` (outcome `already_present`, no processing);
- known content, no PDF: `queued → mapping → ready` (outcome `pdf_attached`, highlights `exact`
  or `mismatch`; parse and chunk run inside `mapping`, never embedding);
- re-process: `queued → parsing → chunking → embedding → ready` (outcome `reprocessed`,
  highlights `exact`); old passages are replaced only at the end;
- any state → `failed` with an error (a failed re-process leaves the paper unchanged). Jobs live in memory only (lost on restart; the library
itself is unaffected because the engine writes atomically).

### AppState

`state` (`loading`, `ready`, `error`), `error_reason`, the job registry, the single ingest
worker, and subscribers of the jobs event stream.

## Browser-side entities (frontend, not persisted except where noted)

| Entity | Fields | Notes |
|---|---|---|
| Conversation | turns [{question, answer}], selected paper ids | lives for the page session (spec) |
| AnswerView | the API `Answer` + `revealed` flag | presentation state per FR-005/FR-011 |
| SourceView | passage, current page, highlight found | opened from a chip |
| UsageView | used, limit, remaining, resets_at, model, model_is_free | refreshed after each question and every 60 s |
| Selection | selected paper ids | stored in `localStorage` as a convenience (wrapped in try/catch) |

## Relationships

- A paper has many passages; each passage has 0..n regions on 1–2 pages.
- A paper has 0..1 stored PDF and 0..1 layout file (layout requires the PDF).
- An answer references numbered passages; each citation chip `[n]` maps to passage n.
- An upload job produces 0..1 paper (outcome `added`) or refers to an existing one.
