"""Separate libraries for experiments that change how passages are embedded (research R6).

The prefix experiment re-ingests the PDFs in `papers/` into `data/eval/libraries/prefix/`, its own
LIBRARY_DIR, so the researcher's library and saved results are never touched (FR-008, SC-009).
USAGE_DIR stays at the main library, so any request still counts against the one daily limit.
"""

import contextlib
import hashlib
import json
import os
from collections.abc import Iterator
from pathlib import Path

from paperpilot import library
from paperpilot.config import load_settings

PREFIX_DIR = Path("data") / "eval" / "libraries" / "prefix"
PAPERS_DIR = Path("papers")
MARKER = "built.json"


@contextlib.contextmanager
def using_library(root: Path | str, embed_prefix: bool = False) -> Iterator[None]:
    """Point the engine at another library for the duration, with usage counted in the main one."""
    main = load_settings()
    env = {"LIBRARY_DIR": str(root), "USAGE_DIR": str(main.usage_dir),
           "EMBED_PREFIX": "true" if embed_prefix else "false"}
    saved = {name: os.environ.get(name) for name in env}
    os.environ.update(env)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _wanted(papers_dir: Path) -> dict:
    """What the built library must match to be reused: the PDFs and the settings that shape passages."""
    settings = load_settings()
    return {
        "embed_prefix": True, "embed_model": settings.embed_model, "chunk_words": settings.chunk_words,
        "chunk_overlap": settings.chunk_overlap, "min_chunk_words": settings.min_chunk_words,
        "pdfs": {pdf.name: hashlib.sha256(pdf.read_bytes()).hexdigest() for pdf in sorted(papers_dir.glob("*.pdf"))},
    }


def build_prefix_library(root: Path | str = PREFIX_DIR, papers_dir: Path | str = PAPERS_DIR) -> Path:
    """Build the prefix library from the PDFs, or reuse it when built for the same PDFs and settings.
    Raises ValueError when `root` is the main library."""
    root, papers_dir = Path(root), Path(papers_dir)
    if root.resolve() == load_settings().library_dir.resolve():
        raise ValueError(f"{root} is the main library; the prefix library needs its own folder")
    wanted = _wanted(papers_dir)
    marker = root / MARKER
    if marker.exists() and json.loads(marker.read_text(encoding="utf-8")) == wanted:
        return root
    with using_library(root, embed_prefix=True):
        for paper in library.list_papers():  # built for other settings: start again
            library.delete_paper(paper.paper_id)
        for pdf in sorted(papers_dir.glob("*.pdf")):
            library.add_paper(pdf)
    marker.write_text(json.dumps(wanted, indent=2) + "\n", encoding="utf-8")
    return root
