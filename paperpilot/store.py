"""Local embeddings and the persistent passage store (research R9, R10, ADR-0001)."""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.api.client import SharedSystemClient
from chromadb.config import Settings as ChromaSettings

from paperpilot.config import load_settings
from paperpilot.ingest import Passage

logger = logging.getLogger(__name__)

# BGE retrieval instruction: added to queries only, never to passages (model card).
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
BATCH_SIZE = 32
COLLECTION = "passages"

_model = None  # SentenceTransformer, loaded on first use
_collections: dict[Path, chromadb.Collection] = {}  # one per library folder
# Held by every library write (upsert, delete, replacing a paper's passages); searches don't
# take it. Reentrant so a caller can hold it across a delete and an upsert (research R3).
write_lock = threading.RLock()


@dataclass(frozen=True)
class Hit:
    """A stored passage returned by a query, with its 0-1 similarity score."""

    passage_id: str
    text: str
    metadata: dict
    score: float


def load_model() -> float:
    """Load the embedding model if needed; return the load time in seconds (0.0 if loaded)."""
    global _model
    if _model is not None:
        return 0.0
    # Imported here: sentence-transformers pulls in torch, which is slow to import.
    from sentence_transformers import SentenceTransformer

    start = time.perf_counter()
    model_name = load_settings().embed_model
    _model = SentenceTransformer(model_name, device="cpu")
    seconds = time.perf_counter() - start
    logger.info("Loaded embedding model %s in %.2fs", model_name, seconds)
    return seconds


def embed_passages(
    texts: list[str], on_progress: Callable[[int, int], None] | None = None
) -> list[list[float]]:
    """Embed passage texts as normalised vectors (no instruction prefix).

    `on_progress(done, total)`, if given, is called after each batch (upload progress, FR-017).
    """
    load_model()
    start = time.perf_counter()
    if on_progress is None:
        vectors = _model.encode(texts, batch_size=BATCH_SIZE, normalize_embeddings=True, show_progress_bar=False)
        result = vectors.tolist()
    else:
        result = []
        for first in range(0, len(texts), BATCH_SIZE):
            batch = texts[first : first + BATCH_SIZE]
            vectors = _model.encode(batch, batch_size=BATCH_SIZE, normalize_embeddings=True, show_progress_bar=False)
            result.extend(vectors.tolist())
            on_progress(first + len(batch), len(texts))
    logger.info("Embedded %d passages in %.2fs", len(texts), time.perf_counter() - start)
    return result


def embed_query(text: str) -> list[float]:
    """Embed a search query as a normalised vector, with the BGE query instruction."""
    load_model()
    return _model.encode(QUERY_PREFIX + text, normalize_embeddings=True).tolist()


def get_collection() -> chromadb.Collection:
    """Return the passage collection in LIBRARY_DIR, opening it once per folder."""
    library_dir = load_settings().library_dir.resolve()
    collection = _collections.get(library_dir)
    if collection is None:
        library_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=library_dir, settings=ChromaSettings(anonymized_telemetry=False))
        collection = client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
        _collections[library_dir] = collection
    return collection


def reset_cache() -> None:
    """Forget open collections so the next call reopens them from disk (like a restart)."""
    _collections.clear()
    SharedSystemClient.clear_system_cache()


def distance_to_score(distance: float) -> float:
    """Turn a cosine distance into a similarity score clamped to [0, 1], 3 decimals."""
    return round(min(max(1.0 - distance, 0.0), 1.0), 3)


def build_where(paper_ids: list[str] | None, sections: list[str] | None = None) -> dict | None:
    """Return a paper and section filter, or None for the whole library (never an empty $in list)."""
    filters = []
    if paper_ids:
        filters.append({"paper_id": {"$in": list(paper_ids)}})
    if sections:
        filters.append({"section": {"$in": list(sections)}})
    if not filters:
        return None
    return filters[0] if len(filters) == 1 else {"$and": filters}


def has_paper(paper_id: str) -> bool:
    """True if any passage of this paper is stored."""
    return bool(get_collection().get(where={"paper_id": paper_id}, limit=1)["ids"])


def paper_metadata(paper_id: str) -> list[dict]:
    """Return the metadata of every stored passage of a paper (empty if not stored)."""
    return get_collection().get(where={"paper_id": paper_id}, include=["metadatas"])["metadatas"]


def upsert_passages(
    passages: list[Passage], embeddings: list[list[float]], source_file: str, page_count: int
) -> None:
    """Write a paper's passages and embeddings in one operation."""
    start = time.perf_counter()
    with write_lock:
        _upsert(passages, embeddings, source_file, page_count)
    logger.info("Stored %d passages in %.2fs", len(passages), time.perf_counter() - start)


def _upsert(passages: list[Passage], embeddings: list[list[float]], source_file: str, page_count: int) -> None:
    get_collection().upsert(
        ids=[p.passage_id for p in passages],
        embeddings=embeddings,
        documents=[p.text for p in passages],
        metadatas=[
            {
                "paper_id": p.paper_id,
                "title": p.title,
                "section": p.section,
                "page": p.page,
                "position": p.position,
                "word_count": p.word_count,
                "kind": p.kind,
                "source_file": source_file,
                "page_count": page_count,
            }
            for p in passages
        ],
    )


def delete_paper_passages(paper_id: str) -> int:
    """Delete every passage of a paper; return how many were removed."""
    with write_lock:
        collection = get_collection()
        ids = collection.get(where={"paper_id": paper_id})["ids"]
        if ids:
            collection.delete(ids=ids)
    return len(ids)


def paper_passages(paper_id: str) -> list[tuple[str, str]]:
    """Return (passage_id, text) for every stored passage of a paper, in reading order."""
    result = get_collection().get(where={"paper_id": paper_id}, include=["documents", "metadatas"])
    rows = sorted(
        zip(result["ids"], result["documents"], result["metadatas"]), key=lambda row: row[2]["position"]
    )
    return [(passage_id, text) for passage_id, text, _ in rows]


def get_passage(passage_id: str) -> tuple[str, dict] | None:
    """Return (text, metadata) of one stored passage, or None if it is not stored."""
    result = get_collection().get(ids=[passage_id], include=["documents", "metadatas"])
    if not result["ids"]:
        return None
    return result["documents"][0], result["metadatas"][0]


def query(
    embedding: list[float], k: int, paper_ids: list[str] | None = None, sections: list[str] | None = None
) -> list[Hit]:
    """Return up to k passages most similar to the embedding, best first."""
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return []
    start = time.perf_counter()
    result = collection.query(
        query_embeddings=[embedding],
        n_results=min(k, count),
        where=build_where(paper_ids, sections),
        include=["documents", "metadatas", "distances"],
    )
    logger.info("Searched %d passages in %.3fs", count, time.perf_counter() - start)
    return [
        Hit(passage_id, text, metadata, distance_to_score(distance))
        for passage_id, text, metadata, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        )
    ]


def all_metadata() -> list[dict]:
    """Return the metadata of every stored passage."""
    return get_collection().get(include=["metadatas"])["metadatas"]


def all_passages() -> list[tuple[str, str, dict]]:
    """Return (passage_id, text, metadata) for every stored passage."""
    result = get_collection().get(include=["documents", "metadatas"])
    return list(zip(result["ids"], result["documents"], result["metadatas"]))
