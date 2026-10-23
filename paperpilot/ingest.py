"""Read research-paper PDFs and turn them into sections and passages."""

import bisect
import hashlib
import re
from dataclasses import dataclass
from typing import Sequence

# A block wider than this fraction of the page is a full-width band divider.
WIDE_FRACTION = 0.6


@dataclass(frozen=True)
class Block:
    """A paragraph-like piece of text and the page it starts on (1-based)."""

    text: str
    page: int


@dataclass(frozen=True)
class Section:
    """A named section of a paper and its blocks in reading order."""

    name: str
    blocks: list[Block]


@dataclass(frozen=True)
class ParsedPaper:
    """A parsed paper: identity, title and sections (References excluded)."""

    paper_id: str
    title: str
    source_file: str
    page_count: int
    sections: list[Section]


@dataclass(frozen=True)
class Passage:
    """A searchable piece of a paper's text with its location."""

    passage_id: str
    paper_id: str
    title: str
    section: str
    page: int
    position: int
    word_count: int
    text: str


@dataclass(frozen=True)
class Heading:
    """A detected heading: kind is "canonical", "numbered" or "stop"."""

    name: str
    kind: str
    number: int | None


# A hyphen at a line end between two letters: "repre-\nsentation".
_HYPHEN_BREAK = re.compile(r"(?<=[^\W\d_])-[ \t]*\n\s*(?=[^\W\d_])")
_WHITESPACE = re.compile(r"\s+")


def clean(text: str) -> str:
    """Join words hyphenated across line breaks and normalise whitespace."""
    return _WHITESPACE.sub(" ", _HYPHEN_BREAK.sub("", text)).strip()


def paper_id_for(data: bytes) -> str:
    """Return a stable paper ID: the first 12 hex chars of the SHA-1 of the file bytes."""
    return hashlib.sha1(data).hexdigest()[:12]


def order_blocks(blocks: Sequence[tuple], page_width: float) -> list[tuple]:
    """Order a page's blocks for reading: (x0, y0, x1, y1, text, ...) tuples.

    Full-width blocks split the page into horizontal bands. Within each band the left
    column is read top to bottom, then the right column, then the full-width block below.
    """
    middle = page_width / 2

    def is_wide(block: tuple) -> bool:
        return block[2] - block[0] > WIDE_FRACTION * page_width

    dividers = sorted((b for b in blocks if is_wide(b)), key=lambda b: (b[1], b[0]))
    divider_tops = [b[1] for b in dividers]
    bands: list[list[tuple]] = [[] for _ in range(len(dividers) + 1)]
    for block in blocks:
        if not is_wide(block):
            bands[bisect.bisect_right(divider_tops, block[1])].append(block)

    ordered: list[tuple] = []
    for index, band in enumerate(bands):
        left = sorted((b for b in band if b[0] < middle), key=lambda b: (b[1], b[0]))
        right = sorted((b for b in band if b[0] >= middle), key=lambda b: (b[1], b[0]))
        ordered += left + right
        if index < len(dividers):
            ordered.append(dividers[index])
    return ordered
