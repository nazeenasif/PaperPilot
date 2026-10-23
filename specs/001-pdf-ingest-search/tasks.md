---

description: "Task list for 001-pdf-ingest-search"
---

# Tasks: PDF Ingestion and Semantic Search

**Input**: Design documents from `/specs/001-pdf-ingest-search/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/library-api.md, quickstart.md
**ADRs**: history/adr/0001-local-retrieval-stack.md, history/adr/0002-passage-identity-and-chunking.md

**Tests**: Per the constitution (Principle VII), pytest tests are REQUIRED for pure logic and
every story ends with a checkpoint script. Unit tests are written BEFORE the code they test
and must fail first. Library-level tests run offline using a temporary library directory, a
fake embedder, and small PDFs generated in the test (no network, no model, no real papers).

**Organization**: Tasks are grouped by user story. US1–US3 (all P1) form the MVP.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 map to the user stories in spec.md
- Every task is one commit. Public functions get type hints and a short docstring.

## Path Conventions

Single package at repo root: `paperpilot/`, `scripts/`, `tests/`, `docs/` (see plan.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Python 3.12 environment, repo hygiene, dependencies

- [X] T001 Install Python 3.12 (`winget install Python.Python.3.12`), create the venv with `py -3.12 -m venv .venv`, activate it, and confirm `python --version` prints 3.12.x (creates `.venv/`, untracked)
- [X] T002 [P] Create `.gitignore` ignoring `.env`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.pdf`, `papers/`, `data/` (Principle VI)
- [X] T003 [P] Create `requirements.txt` listing `pymupdf`, `chromadb`, `sentence-transformers`, `python-dotenv`, `pytest` (unpinned for now) and run `pip install -r requirements.txt` inside `.venv`
- [X] T004 [P] Create `pyproject.toml` with only a `[tool.pytest.ini_options]` section (`testpaths = ["tests"]`, `pythonpath = ["."]`), plus empty `paperpilot/__init__.py`, `scripts/` and `tests/` directories
- [X] T005 [P] Create `.env.example` documenting `CHUNK_WORDS=220`, `CHUNK_OVERLAP=40`, `MIN_CHUNK_WORDS=30`, `TOP_K=6`, `LIBRARY_DIR=data/library`, `EMBED_MODEL=BAAI/bge-small-en-v1.5`, one comment line each

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared errors and settings used by every story. Ends with Checkpoint 0.

- [X] T006 [P] Create `paperpilot/errors.py` with `PaperPilotError(Exception)` and subclasses `SettingsError`, `PdfReadError`, `NoTextError`, `UnknownPaperError`, `EmptyQueryError`, `StorageError` (contracts/library-api.md, Errors table)
- [X] T007 [P] Write failing tests in `tests/test_settings.py`: defaults when no env vars set (use `monkeypatch.delenv`); env overrides parsed as ints/Path; `SettingsError` whose message contains the variable name and value for a non-integer, zero/negative values, `CHUNK_OVERLAP >= CHUNK_WORDS`, `MIN_CHUNK_WORDS >= CHUNK_WORDS`, empty `EMBED_MODEL`; `Settings` is frozen; `describe()` lists every field
- [X] T008 Implement `paperpilot/config.py`: frozen dataclass `Settings` (fields per data-model.md), `load_settings() -> Settings` that calls `dotenv.load_dotenv()` then reads env vars with defaults and validates (raise `SettingsError` naming variable and value), and `Settings.describe() -> str`; make T007 pass
- [X] T009 Create `scripts/checkpoint_0_settings.py`: call `load_settings()`, print `describe()`, print `PASS: settings loaded` or `FAIL: <error>` and exit non-zero on failure — **Checkpoint 0** (SC-001)

**Checkpoint**: `pytest tests/test_settings.py` passes and `python scripts/checkpoint_0_settings.py` prints PASS.

---

## Phase 3: User Story 1 — Add a paper and search it by meaning (Priority: P1) 🎯 MVP

**Goal**: Add a text-based PDF and get the top-k passages for a natural-language query, each
with title, section, page and a 0–1 score; scanned PDFs give a clear error; failed adds leave
nothing behind.

**Independent Test**: Add "Attention Is All You Need", search "what dataset was used for
evaluation?", and confirm relevant results with correct title/section/page/score.

### Tests for User Story 1 (write first, confirm they fail)

- [X] T010 [P] [US1] Write failing tests in `tests/test_clean.py` for `clean()` (`"repre-\nsentation"` → `"representation"`; `"2-\n3"` unchanged except newline → space; newlines become spaces; runs of whitespace collapse; result stripped) and `paper_id_for()` (`paper_id_for(b"")` == `"da39a3ee5e6b"`; length 12; same bytes → same ID)
- [X] T011 [P] [US1] Write failing tests in `tests/test_order.py` for `order_blocks(blocks, page_width)` using synthetic `(x0, y0, x1, y1, text)` tuples: two-column page returns all left-column blocks (top to bottom) then right-column blocks; a full-width title/abstract block at the top comes first, then the columns below it; a full-width caption in the middle of a two-column page splits the page into bands, giving left-above, right-above, caption, left-below, right-below; single-column page (all blocks wide) keeps y order
- [X] T012 [P] [US1] Write failing tests in `tests/test_headings.py` for `detect_heading(line, last_number)`: canonical headings with and without numbering (`"Abstract"`, `"1 Introduction"`, `"2. Related Work"`, `"III. METHODOLOGY"`) mapped to canonical names (`Method/Methods/Methodology/Approach` → `"Methods"`, `Conclusion/Conclusions` → `"Conclusion"`); numbered top-level headings (`"3 Model Architecture"` after 2 → `"Model Architecture"`, `"5. Training"` after 4); a missing heading is tolerated: after 3, `"5 Training"` is detected (gap of 2) and then `"6 Results"` after 5; rejects sub-headings (`"3.1 Encoder"`), table rows (`"2 0.5 1.3"`), sentences ending with a period, lines over 8 words, numbers not greater than the previous (`"2 Model Details"` after 3) or more than 2 higher (`"7 Results Table"` after 2); stop kind for `"References"`, `"Bibliography"`, `"6 References"`
- [X] T013 [P] [US1] Write failing tests in `tests/test_sections.py` for `build_sections(blocks)` (list of `Block(text, page)`): text before the first heading → `"Front Matter"`; heading sharing a block with its paragraph is split off; blocks under 25 characters dropped unless their first line is a heading; everything from References onward excluded; paper with no headings → single `"Front Matter"` section; empty sections are dropped
- [X] T014 [P] [US1] Write failing tests in `tests/test_title.py` for `choose_title(meta_title, page1_blocks, file_stem)`: good metadata title wins; empty, `"Untitled"`, `"Microsoft Word - x.docx"`, `"paper.pdf"` metadata rejected; falls back to first page-1 block of 4–30 words that does not start with `"arXiv"` and has no `"@"`; falls back to file stem
- [X] T015 [P] [US1] Write failing tests in `tests/test_chunking.py` for `chunk_sections(sections, paper_id, title, settings)` with small settings (e.g. 20/5/4): whole paragraphs are packed until the budget; only oversized paragraphs are hard-split; overlap words carried only within a section; no passage consists only of overlap words; final leftover under the minimum dropped; IDs are `"{paper_id}-0"`, `"-1"`, … contiguous; `page` is the page of the first non-overlap word; same input → identical output
- [X] T016 [P] [US1] Write failing tests in `tests/test_store_helpers.py` for `distance_to_score(d)` (0 → 1.0, 1 → 0.0, 1.5 → 0.0 clamped, rounded to 3 decimals) and `build_where(paper_ids)` (`None` and `[]` → `None`; `["a"]` → `{"paper_id": {"$in": ["a"]}}`)
- [X] T017 [P] [US1] Create `tests/conftest.py` fixtures: `library_env` (sets `LIBRARY_DIR` to `tmp_path` via `monkeypatch.setenv` and calls `store.reset_cache()` before and after), `fake_embedder` (monkeypatches `store.embed_passages` / `store.embed_query` to deterministic normalised 384-d vectors derived from word hashes), and `make_pdf(path, sections, references=True, blank=False)` that writes a small text PDF with PyMuPDF (`pymupdf.open()`, `page.insert_textbox`) containing numbered headings, paragraphs and an optional References section
- [X] T018 [US1] Write failing tests in `tests/test_library.py` (uses T017 fixtures): `add_paper` returns `AddResult` with `passage_count > 0`; `search` returns ≤ k results sorted by descending score, each score in [0, 1] with title, section, page and text; no result text contains the References content; blank PDF raises `NoTextError` and stores nothing; non-PDF file raises `PdfReadError`; empty/whitespace query raises `EmptyQueryError`; search on an empty library returns `[]`; if `store.upsert_passages` is monkeypatched to raise, `add_paper` raises `StorageError`, `store.has_paper` is False, and a retry without the patch succeeds

### Implementation for User Story 1

- [X] T019 [US1] In `paperpilot/ingest.py`, add frozen dataclasses `Block`, `Section`, `ParsedPaper`, `Passage`, `Heading` (fields per data-model.md) and implement `clean()` and `paper_id_for()` (research R4, R5); make T010 pass
- [X] T020 [US1] In `paperpilot/ingest.py`, implement `order_blocks()` with band ordering: blocks wider than 60% of the page are band dividers; within each band, left-column blocks (top to bottom) then right-column blocks, then the divider (research R2); make T011 pass
- [X] T021 [US1] In `paperpilot/ingest.py`, implement `detect_heading()` with one compiled canonical regex, the numbered top-level rule with the sequence guard (number greater than the previous numbered heading and at most 2 higher; previous = 0 at the start), and the References/Bibliography stop rule (research R7); make T012 pass
- [X] T022 [US1] In `paperpilot/ingest.py`, implement `build_sections()` (short-block filter with heading exemption, heading split, Front Matter, stop at References; research R3, R7); make T013 pass
- [X] T023 [US1] In `paperpilot/ingest.py`, implement `choose_title()` (research R6); make T014 pass
- [X] T024 [US1] In `paperpilot/ingest.py`, implement `parse_pdf(path) -> ParsedPaper`: read bytes (missing/unreadable → `PdfReadError`), `pymupdf.open(stream=...)` (failure → `PdfReadError`), per page `get_text("blocks", sort=True)` keeping type-0 blocks, `order_blocks`, `clean`, `choose_title`, `build_sections`; raise `NoTextError` if no text; log parse time at INFO
- [X] T025 [US1] Create `scripts/checkpoint_1_parse.py <papers_dir>`: for each PDF print paper ID, title, page count, section names with block counts, and the first 300 characters of page 2; print `PASS`/`FAIL` for "at least one section other than Front Matter" and "no passage text after a References heading"; print parse timings — **Checkpoint 1** (SC-002)
- [ ] T026 [US1] In `paperpilot/ingest.py`, implement `chunk_sections()` (research R8, ADR-0002); make T015 pass
- [ ] T027 [US1] Create `scripts/checkpoint_2_chunk.py <papers_dir>`: for each PDF print passage count, average/min/max words, `PASS`/`FAIL` for 40–120 passages and average within ±15% of 200 words, and 3 random passages (fixed seed) with section and page for human review — **Checkpoint 2** (SC-003)
- [ ] T028 [P] [US1] In `paperpilot/store.py`, implement the embedding part: lazily loaded cached `SentenceTransformer(settings.embed_model)` (log load time once), public `load_model() -> float` that loads it if needed and returns the load time in seconds (0.0 if already loaded), `embed_passages(texts)` (`normalize_embeddings=True`, `batch_size=32`, no prefix) and `embed_query(text)` (prefix `"Represent this sentence for searching relevant passages: "`) (research R9)
- [ ] T029 [US1] In `paperpilot/store.py`, implement the ChromaDB part: `get_collection()` (`PersistentClient(path=settings.library_dir, settings=Settings(anonymized_telemetry=False))`, collection `"passages"` with `{"hnsw:space": "cosine"}`, cached), `reset_cache()`, `distance_to_score()`, `build_where()`, `has_paper()`, `upsert_passages()`, `delete_paper_passages()`, `query(embedding, k, paper_ids)` (`n_results = min(k, count)`, `[]` when empty), `all_metadata()`; log store/search timings (research R10); make T016 pass
- [ ] T030 [US1] Implement `paperpilot/library.py` `add_paper(path)` (parse → chunk → embed in memory → one `upsert_passages`; on write error `delete_paper_passages` then raise `StorageError`; return `AddResult` with timings) and `search(query, k=None, paper_ids=None)` over the whole library (validate query and k, `embed_query`, `store.query`, build `SearchResult` list with ranks); dataclasses `AddResult`, `SearchResult`; make T018 pass
- [ ] T031 [US1] Create `scripts/checkpoint_3_search.py <papers_dir>`: first call `store.load_model()` and print the model load time on its own line (excluded from all checks); then add every PDF (print title, passage count, timings), search `"what dataset was used for evaluation?"`, print top-k with rank, score, title, section, page and first 200 characters; print `PASS`/`FAIL` for ≤ k results, descending scores, scores in [0, 1], warm add time < 60 s per paper (SC-010), warm search time < 2 s (SC-011); print whether the top score is inside the 0.45–0.8 band as INFO only — **Checkpoint 3, US1 part** (SC-004)

**Checkpoint**: `pytest` passes; checkpoints 1–3 run on the 5 test papers and samples look right.

---

## Phase 4: User Story 2 — Re-adding a paper never duplicates data (Priority: P1)

**Goal**: Adding a file whose content is already in the library writes nothing and says so.

**Independent Test**: Add the same PDF twice (and a renamed copy); paper and passage counts are
unchanged.

- [ ] T032 [US2] Add failing tests to `tests/test_library.py`: second `add_paper` of the same file returns `already_present=True` with the same `paper_id` and passage count, and the collection count is unchanged; a byte-identical copy under another file name is also `already_present=True`
- [ ] T033 [US2] In `paperpilot/library.py`, make `add_paper` compute `paper_id_for(bytes)` first and return `AddResult(already_present=True, ...)` via `store.has_paper()` before parsing or embedding (FR-004); make T032 pass
- [ ] T034 [US2] Extend `scripts/checkpoint_3_search.py` with a duplicate section: re-add every PDF, print `PASS`/`FAIL` that each returns `already_present=True` and the total passage count is unchanged — **Checkpoint 3, US2 part** (SC-007)

---

## Phase 5: User Story 3 — Library persists across restarts (Priority: P1)

**Goal**: Papers added in one run are listed and searchable in the next without re-adding.

**Independent Test**: Add a paper, restart Python, run the same search; results match.

- [ ] T035 [US3] Add failing test to `tests/test_library.py`: add a paper, run a search, call `store.reset_cache()` (simulates a restart: new client on the same directory), run the same search, and assert the same passage IDs in the same order and that `has_paper` is still True
- [ ] T036 [US3] In `paperpilot/store.py`, make `get_collection()` create `settings.library_dir` with `parents=True, exist_ok=True` and cache one client per resolved path so `reset_cache()` followed by `get_collection()` reopens the on-disk data; make T035 pass
- [ ] T037 [US3] Extend `scripts/checkpoint_3_search.py`: after the search, save `{query, passage_ids, scores}` to `data/checkpoint3_last.json`; when run with no `papers_dir` argument, add nothing, rerun the query and print `PASS`/`FAIL` that passage IDs and order match the saved file — **Checkpoint 3, US3 part** (SC-006)

**Checkpoint (MVP complete)**: US1–US3 pass `pytest` and Checkpoint 3 (both runs).

---

## Phase 6: User Story 4 — Search within selected papers (Priority: P2)

**Goal**: Restrict a search to one or more paper IDs.

**Independent Test**: With ≥ 2 papers, a search filtered to one paper returns only that paper.

- [ ] T038 [US4] Add failing tests to `tests/test_library.py`: filter to one paper → every result has that `paper_id`; filter to two papers → every result is from one of them; `paper_ids=[]` behaves like no filter; an unknown ID raises `UnknownPaperError` whose message names the ID
- [ ] T039 [US4] In `paperpilot/library.py`, make `search` validate each ID in `paper_ids` with `store.has_paper()` (raise `UnknownPaperError`) and pass `paper_ids` to `store.query` (which uses `build_where`, never an empty `$in`) (FR-016); make T038 pass
- [ ] T040 [US4] Extend `scripts/checkpoint_3_search.py` with a filtered search for each paper: print `PASS`/`FAIL` that 100% of results come from that paper — **Checkpoint 3, US4 part** (SC-005)

---

## Phase 7: User Story 5 — List and delete papers (Priority: P3)

**Goal**: See papers with passage counts; delete a paper and all of its passages.

**Independent Test**: Add two papers, list, delete one, list again, and confirm search no
longer returns it.

- [ ] T041 [US5] Add failing tests to `tests/test_library.py`: `list_papers()` returns one `PaperSummary` per paper sorted by title with correct `passage_count`, `source_file`, `page_count`, and `[]` for an empty library; `delete_paper(id)` returns the number of passages removed, the paper disappears from `list_papers()` and from search results; deleting an unknown ID raises `UnknownPaperError` and changes nothing
- [ ] T042 [US5] In `paperpilot/library.py`, implement `list_papers()` by aggregating `store.all_metadata()` by `paper_id` into `PaperSummary` (FR-017); make the list tests in T041 pass
- [ ] T043 [US5] In `paperpilot/library.py`, implement `delete_paper(paper_id)` using `store.has_paper()` and `store.delete_paper_passages()` (FR-018); make the remaining T041 tests pass
- [ ] T044 [US5] Extend `scripts/checkpoint_3_search.py` with a library section: print the `list_papers()` table (ID, title, passages); delete one paper, print `PASS`/`FAIL` that it is gone from the list and from a search, then re-add it and check the counts are restored — **Checkpoint 3, US5 part**

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T045 Run `pytest` and every command in `specs/001-pdf-ingest-search/quickstart.md` on a fresh `LIBRARY_DIR` with the 5 test papers; fix any drift in `specs/001-pdf-ingest-search/quickstart.md` and record timings in the PHR
- [ ] T046 Pin exact versions of the direct dependencies in `requirements.txt` (`==` from `pip freeze`) and write `docs/known-limitations.md` covering: regex heading detection (missed unnumbered non-standard headings, occasional false numbered headings), heuristic titles, messy equations/tables, scanned PDFs (no OCR), two-column band heuristic (three-column or sidebar layouts, narrow figures inside one column), heading sequence guard can skip a heading after a gap larger than 2, hyphenated compounds at line ends, appendices after References excluded, revised paper versions get a new ID, hard crash during write may leave a partial paper (delete and re-add), score band is a guide not a threshold (FR-020, SC-009)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 first; T002–T005 then in parallel (T003 needs the venv from T001).
- **Foundational (Phase 2)**: needs Setup; blocks all stories.
- **US1 (Phase 3)**: needs Foundational.
- **US2, US3, US4, US5**: each needs US1 (they extend `library.py`, `store.py`, `tests/test_library.py` and `scripts/checkpoint_3_search.py`); they do not depend on each other, but they edit the same files, so do them in priority order: US2 → US3 → US4 → US5.
- **Polish (Phase 8)**: needs all stories; T046 is last.

### Within User Story 1

- Tests T010–T017 first (parallel), then T018 (needs T017 fixtures).
- `ingest.py` tasks are sequential: T019 → T020 → T021 → T022 → T023 → T024 → T026.
- T025 needs T024; T027 needs T026.
- T028 can run in parallel with T019–T027 (different file); T029 follows T028.
- T030 needs T024, T026, T029; T031 needs T030.

### Parallel Opportunities

- Setup: T002, T003, T004, T005.
- Foundational: T006, T007.
- US1 tests: T010–T017 together; T028 alongside the `ingest.py` chain.

## Parallel Example: User Story 1

```text
# Write all US1 unit tests together:
T010 tests/test_clean.py
T011 tests/test_order.py
T012 tests/test_headings.py
T013 tests/test_sections.py
T014 tests/test_title.py
T015 tests/test_chunking.py
T016 tests/test_store_helpers.py
T017 tests/conftest.py

# While the ingest.py chain (T019–T026) runs, build embeddings:
T028 paperpilot/store.py (embedding part)
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US3, all P1)

1. Phase 1 Setup → Phase 2 Foundational (Checkpoint 0).
2. US1 (Checkpoints 1, 2, 3) → **validate**: add and search work end to end.
3. US2 (no duplicates) → US3 (persistence) → **MVP complete**.

### Incremental Delivery

4. US4 filtered search → validate with Checkpoint 3.
5. US5 list/delete → validate with Checkpoint 3.
6. Polish: full quickstart run, pin dependencies, limitations doc.

## Notes

- Verify each test fails before implementing; commit after each task.
- Never commit PDFs, `.env`, `.venv/` or `data/` (Principle VI).
- No LLM, no LangChain anywhere in this feature.
