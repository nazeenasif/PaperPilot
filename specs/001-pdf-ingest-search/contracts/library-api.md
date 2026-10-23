# Contract: `paperpilot.library` (public Python API)

**Feature**: 001-pdf-ingest-search. This feature has no network API (out of scope); the
contract is the set of public functions that checkpoint scripts and later features
(`service.py`) call. Types are defined in [data-model.md](../data-model.md).

## Errors

All user-facing failures raise a subclass of `PaperPilotError` with a readable message.

| Error | Raised when | Spec |
|---|---|---|
| `SettingsError` | a setting is invalid (message names variable and value) | FR-002 |
| `PdfReadError` | file missing, not a PDF, corrupt, or cannot be opened | Edge cases |
| `NoTextError` | the PDF yields no extractable text (e.g. scanned) | FR-013 |
| `UnknownPaperError` | a delete or search filter names a paper ID not in the library | US4, US5 |
| `EmptyQueryError` | search query is empty or whitespace | Edge cases |
| `StorageError` | writing to the library failed (partial data already removed) | FR-004a |

## Functions

### `add_paper(path: str | Path) -> AddResult`

- Computes the paper ID from file bytes. If present: returns `already_present=True`, writes
  nothing.
- Otherwise parses, chunks, embeds, then writes all passages in one operation.
- Errors: `PdfReadError`, `NoTextError`, `StorageError`. On any error nothing for this paper
  remains stored.

### `search(query: str, k: int | None = None, paper_ids: list[str] | None = None) -> list[SearchResult]`

- `k` defaults to `Settings.top_k`; must be > 0.
- `paper_ids=None` or `[]` → search the whole library; otherwise only those papers.
- Returns at most `k` results, ordered by descending score; fewer if fewer passages exist;
  `[]` for an empty library.
- Errors: `EmptyQueryError`, `UnknownPaperError` (any ID in `paper_ids` not in the library).

### `list_papers() -> list[PaperSummary]`

- One entry per paper, sorted by title. `[]` for an empty library.

### `delete_paper(paper_id: str) -> int`

- Removes all passages for the paper; returns the number removed.
- Errors: `UnknownPaperError`.

## Internal module contracts (for unit tests)

`paperpilot.ingest` (pure functions, no model or store):

- `clean(text: str) -> str`
- `paper_id_for(data: bytes) -> str`
- `detect_heading(line: str, last_number: int | None) -> Heading | None` — returns name, kind
  (`canonical` / `numbered` / `stop`) and number.
- `chunk_sections(sections: list[Section], paper_id: str, title: str, settings: Settings) -> list[Passage]`
- `parse_pdf(path: Path) -> ParsedPaper` (uses PyMuPDF)

`paperpilot.store`:

- `load_model() -> float` (loads the model if needed; returns load seconds, 0.0 if already loaded)
- `embed_passages(texts: list[str]) -> list[list[float]]`, `embed_query(text: str) -> list[float]`
- `has_paper`, `upsert_passages`, `delete_paper_passages`, `query`, `all_metadata`
