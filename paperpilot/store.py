"""Local embeddings and the persistent passage store (research R9, R10, ADR-0001)."""

import logging
import time
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


def embed_passages(texts: list[str]) -> list[list[float]]:
    """Embed passage texts as normalised vectors (no instruction prefix)."""
    load_model()
    start = time.perf_counter()
    vectors = _model.encode(texts, batch_size=BATCH_SIZE, normalize_embeddings=True, show_progress_bar=False)
    logger.info("Embedded %d passages in %.2fs", len(texts), time.perf_counter() - start)
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    """Embed a search query as a normalised vector, with the BGE query instruction."""
    load_model()
    return _model.encode(QUERY_PREFIX + text, normalize_embeddings=True).tolist()


def get_collection() -> chromadb.Collection:
    """Return the passage collection in LIBRARY_DIR, opening it once per folder."""
    library_dir = load_settings().library_dir.resolve()
    collection = _collections.get(library_dir)
    if collection is None:
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


def build_where(paper_ids: list[str] | None) -> dict | None:
    """Return a paper filter, or None for the whole library (never an empty $in list)."""
    if not paper_ids:
        return None
    return {"paper_id": {"$in": list(paper_ids)}}


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
    logger.info("Stored %d passages in %.2fs", len(passages), time.perf_counter() - start)


def delete_paper_passages(paper_id: str) -> int:
    """Delete every passage of a paper; return how many were removed."""
    collection = get_collection()
    ids = collection.get(where={"paper_id": paper_id})["ids"]
    if ids:
        collection.delete(ids=ids)
    return len(ids)


def query(embedding: list[float], k: int, paper_ids: list[str] | None = None) -> list[Hit]:
    """Return up to k passages most similar to the embedding, best first."""
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return []
    start = time.perf_counter()
    result = collection.query(
        query_embeddings=[embedding],
        n_results=min(k, count),
        where=build_where(paper_ids),
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
