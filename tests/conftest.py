"""Shared fixtures: a temporary library, a fake embedder, and generated test PDFs.

Library tests run offline: no embedding model, no network, no real papers. The fake
embedder replaces `store.embed_passages`, `store.embed_query` and `store.load_model`, so
`library` must call them through the `store` module (e.g. `store.embed_query(...)`).
`paperpilot.store` is imported inside fixtures only, so tests that do not use these
fixtures still run when `store` is missing or broken.
"""

import hashlib
import math
import re
from pathlib import Path

import pymupdf
import pytest

EMBED_DIM = 384

DEFAULT_SECTIONS = [
    (
        "Abstract",
        "We study how research papers can be split into passages and searched by meaning. "
        "Our system reads each paper, finds its sections, and stores short passages with "
        "their page numbers so that every search result can be traced back to its source. "
        "We show that simple rules work well on typical conference papers.",
    ),
    (
        "1 Introduction",
        "Researchers read many papers and often need to find one detail quickly. Keyword "
        "search misses passages that use different words for the same idea. Semantic search "
        "compares meanings instead of exact words. In this paper we describe a small local "
        "library that adds papers once and answers natural language questions with passages.",
    ),
    (
        "2 Method",
        "We evaluate the system on a benchmark dataset of questions about five papers. The "
        "evaluation dataset contains questions written by researchers together with the "
        "passages that answer them. Each paper is split into passages of about two hundred "
        "words, embedded with a small model, and stored in a persistent vector database.",
    ),
    (
        "3 Results",
        "The system returns a relevant passage among the first six results for most "
        "questions. Results are best for questions about methods and datasets, and weakest "
        "for questions about numbers inside tables. Adding a paper takes a few seconds on a "
        "laptop processor, and a search over the whole library finishes well under a second.",
    ),
]

REFERENCES = (
    "[1] A. Author and B. Writer. refonlytoken A referenced paper about citations. "
    "Proceedings of a Conference, 2020."
)

PAGE_BOTTOM = 790.0


def write_pdf(
    path: Path,
    sections: list[tuple[str, str]] | None = None,
    references: bool = True,
    blank: bool = False,
    title: str = "A Study of Searching Research Papers by Meaning",
) -> Path:
    """Write a small single-column text PDF with headings, paragraphs and references."""
    doc = pymupdf.open()
    if blank:
        doc.new_page()
        doc.save(path)
        return path

    page = doc.new_page()
    y = 50.0

    def add(text: str, size: float, height: float) -> None:
        nonlocal page, y
        if y + height > PAGE_BOTTOM:
            page = doc.new_page()
            y = 50.0
        rect = pymupdf.Rect(50, y, 545, y + height)
        if page.insert_textbox(rect, text, fontsize=size) < 0:
            raise ValueError(f"text does not fit in its box: {text[:40]!r}")
        y += height + 12

    add(title, 16, 30)
    for heading, body in sections if sections is not None else DEFAULT_SECTIONS:
        add(heading, 12, 24)
        add(body, 10, 110)
    if references:
        add("References", 12, 24)
        add(REFERENCES, 10, 40)

    doc.set_metadata({"title": title})
    doc.save(path)
    return path


@pytest.fixture
def make_pdf():
    """Return `write_pdf(path, sections=None, references=True, blank=False, title=...)`."""
    return write_pdf


@pytest.fixture
def library_env(tmp_path, monkeypatch):
    """Point the library at a fresh temporary folder with default settings."""
    from paperpilot import store

    library_dir = tmp_path / "library"
    for name, value in {
        "CHUNK_WORDS": "220",
        "CHUNK_OVERLAP": "40",
        "MIN_CHUNK_WORDS": "30",
        "TOP_K": "6",
        "EMBED_MODEL": "BAAI/bge-small-en-v1.5",
        "LIBRARY_DIR": str(library_dir),
    }.items():
        monkeypatch.setenv(name, value)
    store.reset_cache()
    yield library_dir
    store.reset_cache()


def fake_vector(text: str) -> list[float]:
    """Deterministic normalised bag-of-words vector; shared words mean higher similarity."""
    vector = [0.0] * EMBED_DIM
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        index = int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBED_DIM
        vector[index] += 1.0
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        vector[0] = 1.0
        return vector
    return [v / norm for v in vector]


@pytest.fixture
def fake_embedder(monkeypatch):
    """Replace the embedding model with `fake_vector` (no download, no torch)."""
    from paperpilot import store

    monkeypatch.setattr(store, "load_model", lambda: 0.0)
    monkeypatch.setattr(store, "embed_passages", lambda texts: [fake_vector(t) for t in texts])
    monkeypatch.setattr(store, "embed_query", fake_vector)
