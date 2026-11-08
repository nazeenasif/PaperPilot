"""Public paper-library operations (contracts/library-api.md)."""

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from paperpilot import ingest, store
from paperpilot.config import Settings, load_settings
from paperpilot.errors import (
    EmptyQueryError,
    NoTextError,
    PaperPilotError,
    PdfMissingError,
    PdfReadError,
    StorageError,
    UnknownPaperError,
    UnknownPassageError,
)
from paperpilot.ingest import Region

logger = logging.getLogger(__name__)

PDF_DIR = "pdfs"  # under LIBRARY_DIR: <id>.pdf, <id>.layout.json, <id>.layout-mismatch
NO_TIMINGS = {"parse": 0.0, "embed": 0.0, "store": 0.0}


@dataclass(frozen=True)
class AddResult:
    """Outcome of adding a paper; timings are in seconds (parse, embed, store).

    outcome is "added", "already_present", "pdf_attached" or "reprocessed"; highlights is
    "exact", "mismatch" or "no_pdf" (data-model.md).
    """

    paper_id: str
    title: str
    passage_count: int
    already_present: bool
    timings: dict[str, float]
    outcome: str = "added"
    highlights: str = "exact"


@dataclass(frozen=True)
class PassageLayout:
    """Where a passage is on its pages: the page sizes involved and the regions to highlight."""

    pages: list[dict]  # {"number", "width", "height"}
    regions: list[Region]


@dataclass(frozen=True)
class PassageView:
    """One stored passage for the source viewer (contracts/web-api.md, GET /api/passages)."""

    passage_id: str
    paper_id: str
    title: str
    section: str
    page: int
    page_count: int
    kind: str
    text: str
    has_pdf: bool
    layout: PassageLayout | None
    layout_reason: str | None  # "no_pdf", "mismatch" or "unavailable" when layout is None
    can_reprocess: bool


def _pdf_folder(settings: Settings | None = None) -> Path:
    return (settings or load_settings()).library_dir / PDF_DIR


def _pdf_file(paper_id: str) -> Path:
    return _pdf_folder() / f"{paper_id}.pdf"


def _layout_file(paper_id: str) -> Path:
    return _pdf_folder() / f"{paper_id}.layout.json"


def _mismatch_file(paper_id: str) -> Path:
    return _pdf_folder() / f"{paper_id}.layout-mismatch"


def _write_atomic(path: Path, data: bytes) -> None:
    """Write a file so readers never see a partial one (temporary file, then rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _write_layout(paper: ingest.ParsedPaper, passages: list[ingest.Passage], settings: Settings) -> None:
    layout = ingest.build_layout(paper, passages, settings)
    _write_atomic(_layout_file(paper.paper_id), json.dumps(layout).encode("utf-8"))
    _mismatch_file(paper.paper_id).unlink(missing_ok=True)


def _remove_files(paper_id: str) -> None:
    for path in (_pdf_file(paper_id), _layout_file(paper_id), _mismatch_file(paper_id)):
        path.unlink(missing_ok=True)


def _highlights(paper_id: str) -> str:
    """Highlight status of a paper: "exact" (verified layout), "mismatch" or "no_pdf"."""
    if not _pdf_file(paper_id).exists():
        return "no_pdf"
    return "exact" if _layout_file(paper_id).exists() else "mismatch"


@dataclass(frozen=True)
class SearchResult:
    """One search hit with its 1-based rank and 0-1 similarity score."""

    rank: int
    score: float
    passage_id: str
    paper_id: str
    title: str
    section: str
    page: int
    text: str


@dataclass(frozen=True)
class PaperSummary:
    """One paper in the library, as shown by list_papers()."""

    paper_id: str
    title: str
    source_file: str
    page_count: int
    passage_count: int
    text_passages: int = 0
    table_passages: int = 0
    section_count: int = 0
    arxiv_id: str | None = None
    has_pdf: bool = False
    highlights: str = "no_pdf"  # "exact", "mismatch" or "no_pdf"


def list_papers() -> list[PaperSummary]:
    """Return one summary per stored paper with its card statistics, sorted by title (FR-019).

    Counts come from the stored passage metadata; the arXiv identifier from the stored page-1
    passages, so papers added before Feature 3 have it too without re-parsing.
    """
    papers: dict[str, dict] = {}
    counts: dict[str, dict] = {}
    for _, text, metadata in store.all_passages():
        paper_id = metadata["paper_id"]
        papers.setdefault(paper_id, metadata)
        stats = counts.setdefault(paper_id, {"passages": 0, "tables": 0, "sections": set(), "arxiv": None})
        stats["passages"] += 1
        stats["tables"] += metadata.get("kind") == "table"
        stats["sections"].add(metadata["section"])
        if stats["arxiv"] is None and metadata["page"] == 1:
            stats["arxiv"] = ingest.find_arxiv_id(text)
    summaries = []
    for paper_id, m in papers.items():
        stats = counts[paper_id]
        summaries.append(PaperSummary(
            paper_id, m["title"], m["source_file"], m["page_count"], stats["passages"],
            text_passages=stats["passages"] - stats["tables"], table_passages=stats["tables"],
            section_count=len(stats["sections"]), arxiv_id=stats["arxiv"],
            has_pdf=_pdf_file(paper_id).exists(), highlights=_highlights(paper_id),
        ))
    return sorted(summaries, key=lambda p: p.title.lower())


def delete_paper(paper_id: str) -> int:
    """Delete a paper and all its passages; return the number removed (FR-018).

    Raises UnknownPaperError if the paper is not in the library.
    """
    if not store.has_paper(paper_id):
        raise UnknownPaperError(f"Paper {paper_id} is not in the library")
    removed = store.delete_paper_passages(paper_id)
    _remove_files(paper_id)
    forget_results(paper_id)
    logger.info("Deleted %s: %d passages", paper_id, removed)
    return removed


Progress = Callable[[str, int | None], None]


def _no_progress(phase: str, percent: int | None) -> None:
    pass


def _embed_with_progress(texts: list[str], report: Progress) -> list[list[float]]:
    """Embed passages, reporting the "embedding" phase from 0 to 100 percent."""
    report("embedding", 0)
    return store.embed_passages(texts, on_progress=lambda done, total: report("embedding", round(100 * done / total)))


def add_paper(path: str | Path, on_progress: Progress | None = None) -> AddResult:
    """Parse, chunk, embed and store a PDF with its PDF copy and highlight layout.

    Nothing is stored if any step fails. Content already in the library is never embedded
    again (FR-018): with its PDF stored it is "already_present"; without, the PDF is attached
    and its layout mapped (parse and chunk only). `on_progress(phase, percent)` reports
    "parsing", "chunking", "embedding" (percent), "mapping" and "ready" (FR-017).
    Raises PdfReadError, NoTextError or StorageError.
    """
    report = on_progress or _no_progress
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise PdfReadError(f"Cannot read {path}: {error.strerror or error}") from error
    paper_id = ingest.paper_id_for(data)
    stored_metadata = store.paper_metadata(paper_id)
    if stored_metadata:
        title = stored_metadata[0]["title"]
        if _pdf_file(paper_id).exists():
            logger.info("%s is already in the library as %s", path.name, paper_id)
            report("ready", None)
            return AddResult(paper_id, title, len(stored_metadata), True, NO_TIMINGS, "already_present",
                             _highlights(paper_id))
        return _attach_pdf(path, data, paper_id, title, len(stored_metadata), report)

    settings = load_settings()
    start = time.perf_counter()
    report("parsing", None)
    paper = ingest.parse_pdf(path)
    report("chunking", None)
    passages = ingest.chunk_sections(paper.sections, paper.paper_id, paper.title, settings)
    if not passages:
        raise NoTextError(f"{paper.source_file} has no passages long enough to store")
    parsed = time.perf_counter()

    # All slow, failure-prone work happens before the writes (research R11).
    embeddings = _embed_with_progress([p.text for p in passages], report)
    embedded = time.perf_counter()
    try:
        store.upsert_passages(passages, embeddings, paper.source_file, paper.page_count)
        _write_atomic(_pdf_file(paper.paper_id), data)
        _write_layout(paper, passages, settings)
    except Exception as error:
        store.delete_paper_passages(paper.paper_id)
        _remove_files(paper.paper_id)
        raise StorageError(f"Could not save {paper.source_file} ({error}); nothing was stored") from error
    stored = time.perf_counter()

    timings = {"parse": parsed - start, "embed": embedded - parsed, "store": stored - embedded}
    logger.info("Added %s: %d passages in %.2fs", paper.source_file, len(passages), stored - start)
    report("ready", None)
    return AddResult(paper.paper_id, paper.title, len(passages), False, timings, "added", "exact")


def _attach_pdf(
    path: Path, data: bytes, paper_id: str, title: str, passage_count: int, report: Progress = _no_progress
) -> AddResult:
    """Store the PDF of a paper already in the library, then map its highlights without
    embedding: the layout is kept only if every regenerated passage id and text matches."""
    settings = load_settings()
    start = time.perf_counter()
    report("mapping", None)
    _write_atomic(_pdf_file(paper_id), data)
    try:
        paper = ingest.parse_pdf(path)
        passages = ingest.chunk_sections(paper.sections, paper.paper_id, paper.title, settings)
        matches = [(p.passage_id, p.text) for p in passages] == store.paper_passages(paper_id)
    except PaperPilotError:
        logger.warning("Could not map highlights for %s", paper_id, exc_info=True)
        matches = False
    if matches:
        _write_layout(paper, passages, settings)
        highlights = "exact"
    else:
        _layout_file(paper_id).unlink(missing_ok=True)
        _write_atomic(_mismatch_file(paper_id), b"stored passages differ from this PDF's passages\n")
        highlights = "mismatch"
    logger.info("Attached the PDF of %s (%s); highlights %s", paper_id, path.name, highlights)
    timings = {"parse": time.perf_counter() - start, "embed": 0.0, "store": 0.0}
    report("ready", None)
    return AddResult(paper_id, title, passage_count, True, timings, "pdf_attached", highlights)


def reprocess_paper(paper_id: str, on_progress: Progress | None = None) -> AddResult:
    """Rebuild a paper from its stored PDF: parse, chunk, embed and lay out again (FR-018a).

    The old passages are replaced only after the new ones are embedded, so a failure leaves
    the paper as it was. Raises UnknownPaperError or PdfMissingError.
    """
    stored_metadata = store.paper_metadata(paper_id)
    if not stored_metadata:
        raise UnknownPaperError(f"Paper {paper_id} is not in the library")
    report = on_progress or _no_progress
    source = pdf_path(paper_id)
    source_file = stored_metadata[0]["source_file"]
    settings = load_settings()
    start = time.perf_counter()
    report("parsing", None)
    paper = ingest.parse_pdf(source)
    report("chunking", None)
    passages = ingest.chunk_sections(paper.sections, paper.paper_id, paper.title, settings)
    if not passages:
        raise NoTextError(f"{source_file} has no passages long enough to store")
    parsed = time.perf_counter()
    embeddings = _embed_with_progress([p.text for p in passages], report)
    embedded = time.perf_counter()
    with store.write_lock:
        store.delete_paper_passages(paper_id)
        store.upsert_passages(passages, embeddings, source_file, paper.page_count)
    _write_layout(paper, passages, settings)
    mark_results_reprocessed(paper_id)  # saved summaries cite the old passages (research R6)
    stored = time.perf_counter()
    logger.info("Re-processed %s: %d passages in %.2fs", paper_id, len(passages), stored - start)
    report("ready", None)
    timings = {"parse": parsed - start, "embed": embedded - parsed, "store": stored - embedded}
    return AddResult(paper_id, paper.title, len(passages), True, timings, "reprocessed", "exact")


def pdf_path(paper_id: str) -> Path:
    """The stored PDF of a paper. Raises UnknownPaperError or PdfMissingError."""
    if not store.has_paper(paper_id):
        raise UnknownPaperError(f"Paper {paper_id} is not in the library")
    path = _pdf_file(paper_id)
    if not path.exists():
        raise PdfMissingError(paper_id)
    return path


def get_passage(passage_id: str) -> PassageView:
    """One stored passage with its highlight layout, for the source viewer.

    Reads the layout file only; it never parses (spec FR-018 as amended). Raises
    UnknownPassageError for an unknown id.
    """
    found = store.get_passage(passage_id)
    if found is None:
        raise UnknownPassageError(f"Passage {passage_id} is not in the library")
    text, meta = found
    paper_id, page = meta["paper_id"], int(meta["page"])
    has_pdf = _pdf_file(paper_id).exists()
    layout, reason = None, None
    if not has_pdf:
        reason = "no_pdf"
    elif not _layout_file(paper_id).exists():
        reason = "mismatch"
    else:
        layout = _passage_layout(paper_id, passage_id, page)
        reason = None if layout is not None else "unavailable"
    return PassageView(
        passage_id, paper_id, meta["title"], meta["section"], page, int(meta["page_count"]),
        meta.get("kind", "text"), text, has_pdf, layout, reason, has_pdf and reason == "mismatch",
    )


def _passage_layout(paper_id: str, passage_id: str, page: int) -> PassageLayout | None:
    """The passage's regions from the layout file, or None if it is missing or unreadable."""
    try:
        document = json.loads(_layout_file(paper_id).read_text(encoding="utf-8"))
        raw = document["passages"].get(passage_id)
        if not raw:
            return None
        regions = [Region(int(r["page"]), r["x0"], r["y0"], r["x1"], r["y1"]) for r in raw]
        wanted = {page} | {r.page for r in regions}
        pages = [p for p in document["pages"] if p["number"] in wanted]
    except (OSError, ValueError, KeyError, TypeError):
        logger.warning("Unreadable layout for %s", paper_id, exc_info=True)
        return None
    return PassageLayout(pages, regions)


def paper_sections(paper_id: str) -> list[str]:
    """The names of a paper's sections that hold stored passages, in passage order."""
    return list(dict.fromkeys(m["section"] for m in store.paper_metadata(paper_id)))


def search(
    query: str, k: int | None = None, paper_ids: list[str] | None = None, sections: list[str] | None = None
) -> list[SearchResult]:
    """Return up to k passages most similar to the query, best first.

    k defaults to TOP_K; an empty paper_ids searches the whole library; `sections` limits the
    search to sections with those exact names.
    Raises EmptyQueryError for an empty or whitespace query and UnknownPaperError if a
    paper ID in paper_ids is not in the library.
    """
    if not query or not query.strip():
        raise EmptyQueryError("The search query is empty")
    k = load_settings().top_k if k is None else k
    if k < 1:
        raise ValueError(f"k must be at least 1, got {k}")
    for paper_id in paper_ids or []:
        if not store.has_paper(paper_id):
            raise UnknownPaperError(f"Paper {paper_id} is not in the library")
    hits = store.query(store.embed_query(query.strip()), k, paper_ids, sections)
    return [
        SearchResult(
            rank=rank,
            score=hit.score,
            passage_id=hit.passage_id,
            paper_id=hit.metadata["paper_id"],
            title=hit.metadata["title"],
            section=hit.metadata["section"],
            page=hit.metadata["page"],
            text=hit.text,
        )
        for rank, hit in enumerate(hits, start=1)
    ]


# --- Saved summaries and comparisons (research R6, ADR-0009) ---

RESULTS_FILE = "results.sqlite3"

_prepared_results_files: set[Path] = set()
_prepare_results_lock = threading.Lock()


@dataclass(frozen=True)
class ResultKey:
    """What a saved result is about: its kind, papers and aspects, in a canonical order."""

    kind: str  # "summary", "summary_unfinished" or "comparison"
    paper_ids: tuple[str, ...]
    aspects: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps([self.kind, self.paper_ids, self.aspects]).encode()).hexdigest()


def result_key(kind: str, paper_ids: list[str], aspects: list[str] | None = None) -> ResultKey:
    """The key for a saved result; paper and aspect order do not matter."""
    return ResultKey(kind, tuple(sorted(paper_ids)), tuple(sorted(aspects or ())))


REPROCESSED = "reprocessed"  # in place of a fingerprint: never matches one


def passage_fingerprint(paper_id: str) -> str:
    """SHA-256 of a paper's stored passage ids and texts, in order: changes when it is re-chunked."""
    digest = hashlib.sha256()
    for passage_id, text in store.paper_passages(paper_id):
        digest.update(passage_id.encode() + b"\0" + text.encode() + b"\0")
    return digest.hexdigest()


def _results_connection(settings: Settings | None = None) -> sqlite3.Connection:
    """The results database; WAL and a busy timeout let the API and scripts share it."""
    settings = settings or load_settings()
    settings.library_dir.mkdir(parents=True, exist_ok=True)
    path = Path(settings.library_dir) / RESULTS_FILE
    db = sqlite3.connect(path, timeout=10.0, isolation_level=None)
    try:
        with _prepare_results_lock:
            if path not in _prepared_results_files:
                for attempt in range(50):  # switching to WAL reports "locked" at once; retry briefly
                    try:
                        if db.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                            db.execute("PRAGMA journal_mode=WAL")
                        break
                    except sqlite3.OperationalError:
                        if attempt == 49:
                            raise
                        time.sleep(0.05)
                db.execute(
                    "CREATE TABLE IF NOT EXISTS results (key TEXT PRIMARY KEY, kind TEXT NOT NULL, "
                    "paper_ids TEXT NOT NULL, aspects TEXT NOT NULL, result TEXT NOT NULL, model TEXT NOT NULL, "
                    "prompt_version INTEGER NOT NULL, fingerprints TEXT NOT NULL, created_at TEXT NOT NULL)"
                )
                _prepared_results_files.add(path)
    except BaseException:
        db.close()
        raise
    return db


def save_result(key: ResultKey, result: dict, model: str, prompt_version: int) -> None:
    """Save (or replace) a result with what it was made from: model, version, passage fingerprints."""
    fingerprints = {paper_id: passage_fingerprint(paper_id) for paper_id in key.paper_ids}
    db = _results_connection()
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "INSERT OR REPLACE INTO results VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (key.digest, key.kind, ",".join(key.paper_ids), ",".join(key.aspects), json.dumps(result), model,
             prompt_version, json.dumps(fingerprints)),
        )
        db.execute("COMMIT")
    finally:
        db.close()


def load_result(key: ResultKey, model: str, prompt_version: int) -> tuple[dict, str | None] | None:
    """The saved result and why it is stale (None when current), or None if nothing is saved.

    Stale reasons: "passages_changed" (the paper was re-processed), "instructions_changed",
    "model_changed" (FR-017).
    """
    db = _results_connection()
    try:
        row = db.execute("SELECT result, model, prompt_version, fingerprints FROM results WHERE key = ?",
                         (key.digest,)).fetchone()
    finally:
        db.close()
    if row is None:
        return None
    result, saved_model, saved_version, fingerprints = json.loads(row[0]), row[1], row[2], json.loads(row[3])
    if any(passage_fingerprint(pid) != fingerprints.get(pid) for pid in key.paper_ids):
        return result, "passages_changed"
    if saved_version != prompt_version:
        return result, "instructions_changed"
    if saved_model != model:
        return result, "model_changed"
    return result, None


def mark_results_reprocessed(paper_id: str) -> int:
    """Mark every saved result that includes the paper as made before it was re-processed, even if
    its passages came out the same (FR-017). The results stay readable. Returns how many."""
    db = _results_connection()
    try:
        db.execute("BEGIN IMMEDIATE")
        rows = [(key, json.loads(prints)) for key, ids, prints
                in db.execute("SELECT key, paper_ids, fingerprints FROM results") if paper_id in ids.split(",")]
        db.executemany("UPDATE results SET fingerprints = ? WHERE key = ?",
                       [(json.dumps({**prints, paper_id: REPROCESSED}), key) for key, prints in rows])
        db.execute("COMMIT")
    finally:
        db.close()
    return len(rows)


def delete_result(key: ResultKey) -> None:
    """Delete one saved result, if there is one."""
    db = _results_connection()
    try:
        db.execute("DELETE FROM results WHERE key = ?", (key.digest,))
    finally:
        db.close()


def forget_results(paper_id: str) -> int:
    """Delete every saved result that includes the paper; return how many (when it is deleted)."""
    db = _results_connection()
    try:
        db.execute("BEGIN IMMEDIATE")
        keys = [k for k, ids in db.execute("SELECT key, paper_ids FROM results") if paper_id in ids.split(",")]
        db.executemany("DELETE FROM results WHERE key = ?", [(k,) for k in keys])
        db.execute("COMMIT")
    finally:
        db.close()
    if keys:
        logger.info("Forgot %d saved result(s) for %s", len(keys), paper_id)
    return len(keys)
