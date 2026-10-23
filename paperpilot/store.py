"""Local embeddings and the persistent passage store (research R9, R10, ADR-0001)."""

import logging
import time

from paperpilot.config import load_settings

logger = logging.getLogger(__name__)

# BGE retrieval instruction: added to queries only, never to passages (model card).
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
BATCH_SIZE = 32

_model = None  # SentenceTransformer, loaded on first use


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
