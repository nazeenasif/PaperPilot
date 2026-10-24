"""Public paper-library operations (contracts/library-api.md)."""

import json
import logging
import os
import time
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


def list_papers() -> list[PaperSummary]:
    """Return one summary per stored paper, sorted by title (FR-017)."""
    papers: dict[str, dict] = {}
    counts: dict[str, int] = {}
    for metadata in store.all_metadata():
        paper_id = metadata["paper_id"]
        papers.setdefault(paper_id, metadata)
        counts[paper_id] = counts.get(paper_id, 0) + 1
    summaries = [
        PaperSummary(paper_id, m["title"], m["source_file"], m["page_count"], counts[paper_id])
        for paper_id, m in papers.items()
    ]
    return sorted(summaries, key=lambda p: p.title.lower())


def delete_paper(paper_id: str) -> int:
    """Delete a paper and all its passages; return the number removed (FR-018).

    Raises UnknownPaperError if the paper is not in the library.
    """
    if not store.has_paper(paper_id):
        raise UnknownPaperError(f"Paper {paper_id} is not in the library")
    removed = store.delete_paper_passages(paper_id)
    _remove_files(paper_id)
    logger.info("Deleted %s: %d passages", paper_id, removed)
    return removed


def add_paper(path: str | Path) -> AddResult:
    """Parse, chunk, embed and store a PDF with its PDF copy and highlight layout.

    Nothing is stored if any step fails. Content already in the library is never embedded
    again (FR-018): with its PDF stored it is "already_present"; without, the PDF is attached
    and its layout mapped (parse and chunk only). Raises PdfReadError, NoTextError or StorageError.
    """
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
            return AddResult(paper_id, title, len(stored_metadata), True, NO_TIMINGS, "already_present",
                             _highlights(paper_id))
        return _attach_pdf(path, data, paper_id, title, len(stored_metadata))

    settings = load_settings()
    start = time.perf_counter()
    paper = ingest.parse_pdf(path)
    passages = ingest.chunk_sections(paper.sections, paper.paper_id, paper.title, settings)
    if not passages:
        raise NoTextError(f"{paper.source_file} has no passages long enough to store")
    parsed = time.perf_counter()

    # All slow, failure-prone work happens before the writes (research R11).
    embeddings = store.embed_passages([p.text for p in passages])
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
    return AddResult(paper.paper_id, paper.title, len(passages), False, timings, "added", "exact")


def _attach_pdf(path: Path, data: bytes, paper_id: str, title: str, passage_count: int) -> AddResult:
    """Store the PDF of a paper already in the library, then map its highlights without
    embedding: the layout is kept only if every regenerated passage id and text matches."""
    settings = load_settings()
    start = time.perf_counter()
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
    return AddResult(paper_id, title, passage_count, True, timings, "pdf_attached", highlights)


def reprocess_paper(paper_id: str) -> AddResult:
    """Rebuild a paper from its stored PDF: parse, chunk, embed and lay out again (FR-018a).

    The old passages are replaced only after the new ones are embedded, so a failure leaves
    the paper as it was. Raises UnknownPaperError or PdfMissingError.
    """
    stored_metadata = store.paper_metadata(paper_id)
    if not stored_metadata:
        raise UnknownPaperError(f"Paper {paper_id} is not in the library")
    source = pdf_path(paper_id)
    source_file = stored_metadata[0]["source_file"]
    settings = load_settings()
    start = time.perf_counter()
    paper = ingest.parse_pdf(source)
    passages = ingest.chunk_sections(paper.sections, paper.paper_id, paper.title, settings)
    if not passages:
        raise NoTextError(f"{source_file} has no passages long enough to store")
    parsed = time.perf_counter()
    embeddings = store.embed_passages([p.text for p in passages])
    embedded = time.perf_counter()
    with store.write_lock:
        store.delete_paper_passages(paper_id)
        store.upsert_passages(passages, embeddings, source_file, paper.page_count)
    _write_layout(paper, passages, settings)
    stored = time.perf_counter()
    logger.info("Re-processed %s: %d passages in %.2fs", paper_id, len(passages), stored - start)
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


def search(query: str, k: int | None = None, paper_ids: list[str] | None = None) -> list[SearchResult]:
    """Return up to k passages most similar to the query, best first.

    k defaults to TOP_K; an empty paper_ids searches the whole library.
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
    hits = store.query(store.embed_query(query.strip()), k, paper_ids)
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
