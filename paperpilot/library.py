"""Public paper-library operations (contracts/library-api.md)."""

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from paperpilot import ingest, store
from paperpilot.config import load_settings
from paperpilot.errors import EmptyQueryError, NoTextError, PdfReadError, StorageError, UnknownPaperError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AddResult:
    """Outcome of adding a paper; timings are in seconds (parse, embed, store)."""

    paper_id: str
    title: str
    passage_count: int
    already_present: bool
    timings: dict[str, float]


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


def add_paper(path: str | Path) -> AddResult:
    """Parse, chunk, embed and store a PDF; nothing is stored if any step fails.

    A file whose content is already in the library is not processed again: the result has
    already_present=True (FR-004). Raises PdfReadError, NoTextError or StorageError.
    """
    path = Path(path)
    try:
        paper_id = ingest.paper_id_for(path.read_bytes())
    except OSError as error:
        raise PdfReadError(f"Cannot read {path}: {error.strerror or error}") from error
    stored_metadata = store.paper_metadata(paper_id)
    if stored_metadata:
        title = stored_metadata[0]["title"]
        logger.info("%s is already in the library as %s", path.name, paper_id)
        return AddResult(paper_id, title, len(stored_metadata), True, {"parse": 0.0, "embed": 0.0, "store": 0.0})

    settings = load_settings()
    start = time.perf_counter()
    paper = ingest.parse_pdf(path)
    passages = ingest.chunk_sections(paper.sections, paper.paper_id, paper.title, settings)
    if not passages:
        raise NoTextError(f"{paper.source_file} has no passages long enough to store")
    parsed = time.perf_counter()

    # All slow, failure-prone work happens before the single write (research R11).
    embeddings = store.embed_passages([p.text for p in passages])
    embedded = time.perf_counter()
    try:
        store.upsert_passages(passages, embeddings, paper.source_file, paper.page_count)
    except Exception as error:
        store.delete_paper_passages(paper.paper_id)
        raise StorageError(f"Could not save {paper.source_file} ({error}); nothing was stored") from error
    stored = time.perf_counter()

    timings = {"parse": parsed - start, "embed": embedded - parsed, "store": stored - embedded}
    logger.info("Added %s: %d passages in %.2fs", paper.source_file, len(passages), stored - start)
    return AddResult(paper.paper_id, paper.title, len(passages), False, timings)


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
