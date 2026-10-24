# Contract: Engine additions for the web app (Feature 3)

All logic stays in the `paperpilot` package (spec FR-001); `api/` only calls these. Existing
signatures keep working (new parameters are optional keyword arguments), so Features 1–2 tests
and checkpoint scripts are unaffected.

## config
- `daily_request_limit: int` ← `DAILY_REQUEST_LIMIT` (default 50, ≥ 1).
- `frontend_origin: str` ← `FRONTEND_ORIGIN` (default `http://127.0.0.1:3000`).

## errors
- `DailyLimitError(LLMError)`: `.used`, `.limit`, `.resets_at` (aware UTC datetime).
- `RateLimitedError(LLMError)`: `.until` (aware UTC datetime), `.daily` (bool). Message:
  "rate limited until <ISO time>".
- `PdfMissingError(PaperPilotError)`: `.paper_id`.

## ingest
- `parse_pdf(path)` additionally records each block's word boxes and page sizes and the
  `arxiv_id`; behaviour and output text unchanged.
- `chunk_sections(...)` fills `Passage.regions` (tuple of `Region(page, x0, y0, x1, y1)`),
  covering every word in the passage, overlap included.
- `build_layout(paper, passages, settings) -> dict` returns the layout-file document.

## store
- `embed_passages(texts, on_progress: Callable[[int, int], None] | None = None)`: calls
  `on_progress(done, total)` after each batch.
- `write_lock`: a process-wide `threading.Lock` held by upsert and delete.

## library
- `add_paper(path, on_progress: Callable[[str, int | None], None] | None = None) -> AddResult`:
  phases `parsing`, `chunking`, `embedding` (percent), `ready`; stores the PDF copy and layout
  after the passages; outcome `added`, or for known content `already_present` (PDF stored) or
  `pdf_attached` (PDF saved, nothing parsed or embedded).
- `delete_paper(paper_id)` also removes the PDF and layout.
- `list_papers()` fills the new `PaperSummary` fields.
- `pdf_path(paper_id) -> Path` — raises `PdfMissingError` / `UnknownPaperError`.
- `get_passage(passage_id) -> PassageView` — layout from the file; built lazily for attached
  PDFs (parse + chunk only, accepted only if every passage id and text matches), else
  `layout=None` with a reason.

## llm
- `generate(system, prompt, on_retry: Callable[[RetryNotice], None] | None = None)`:
  - before any request: `DailyLimitError` if today's usage ≥ limit;
  - every attempt increments the shared daily counter (in addition to `request_counts()`);
  - a hinted wait > 60 s → `RateLimitedError` at once (one request spent);
  - `X-RateLimit-Reset` trusted only if in the future and within 48 h;
  - `on_retry` is called before each retry wait.
- `usage() -> Usage` (`used`, `limit`, `remaining`, `resets_at`, `source`).
- `refresh_usage() -> Usage`: reads `GET /api/v1/key` `free_model_daily_requests` when the
  provider is OpenRouter (not a model request; not counted); on failure keeps the local count.

## service
- `ask(question, paper_ids=None, k=None, history=None, on_event: Callable[[str, dict], None] |
  None = None) -> Answer`: events `rewriting`, `searching`, `reading` (`passages`, `papers`),
  `generating`, `retry_wait` (`attempt`, `max_attempts`, `wait_seconds`, `reason`), `checking`.
  The returned `Answer` is unchanged; callers compute `verified` and `papers_read`.
