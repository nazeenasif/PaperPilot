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


# Optional heading number: "1", "1.", "III.", "A.".
_PREFIX = r"(?:(?P<num>\d{1,2})\.?|[IVXLC]{1,6}\.?|[A-Z]\.)\s+"
_CANONICAL = re.compile(
    rf"^(?:{_PREFIX})?(?P<word>abstract|introduction|related\s+work|background|methods?"
    r"|methodology|approach|experiments|results|discussion|limitations|conclusions?)\s*[.:]?$",
    re.IGNORECASE,
)
_STOP = re.compile(rf"^(?:{_PREFIX})?(?:references|bibliography)\s*[.:]?$", re.IGNORECASE)
# A numbered top-level heading: number, then a capitalised title with no period.
_NUMBERED = re.compile(r"^(?P<num>\d{1,2})\.?\s+(?P<text>[A-Z][A-Za-z][^.]{0,60})$")
_CANONICAL_NAMES = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "related work": "Related Work",
    "background": "Background",
    "method": "Methods",
    "methods": "Methods",
    "methodology": "Methods",
    "approach": "Methods",
    "experiments": "Experiments",
    "results": "Results",
    "discussion": "Discussion",
    "limitations": "Limitations",
    "conclusion": "Conclusion",
    "conclusions": "Conclusion",
}
FRONT_MATTER = "Front Matter"
# Blocks shorter than this (page numbers, running headers) are dropped unless a heading.
MIN_BLOCK_CHARS = 25
MAX_HEADING_WORDS = 8
# Metadata titles that say nothing about the paper.
_GENERIC_TITLE = re.compile(r"^(?:untitled|microsoft word\b.*|.*\.(?:pdf|dvi|docx?|tex))$", re.IGNORECASE)
MIN_TITLE_WORDS, MAX_TITLE_WORDS = 4, 30
# A numbered heading may skip at most one missed heading (e.g. 3 then 5).
MAX_NUMBER_STEP = 2

# A hyphen at a line end between two letters: "repre-\nsentation".
_HYPHEN_BREAK = re.compile(r"(?<=[^\W\d_])-[ \t]*\n\s*(?=[^\W\d_])")
_WHITESPACE = re.compile(r"\s+")


def clean(text: str) -> str:
    """Join words hyphenated across line breaks and normalise whitespace."""
    return _WHITESPACE.sub(" ", _HYPHEN_BREAK.sub("", text)).strip()


def paper_id_for(data: bytes) -> str:
    """Return a stable paper ID: the first 12 hex chars of the SHA-1 of the file bytes."""
    return hashlib.sha1(data).hexdigest()[:12]


def _number(match: re.Match) -> int | None:
    return int(match["num"]) if match["num"] else None


def detect_heading(line: str, last_number: int | None) -> Heading | None:
    """Return the heading on this line, or None.

    `last_number` is the number of the previous numbered heading (None at the start).
    Every returned heading carries its number (or None), so callers can pass it back in.
    """
    line = line.strip()
    if match := _STOP.match(line):
        return Heading("References", "stop", _number(match))
    if match := _CANONICAL.match(line):
        word = " ".join(match["word"].lower().split())
        return Heading(_CANONICAL_NAMES[word], "canonical", _number(match))
    match = _NUMBERED.match(line)
    if not match:
        return None
    number, text = int(match["num"]), match["text"].strip()
    previous = last_number or 0
    if len(text.split()) > MAX_HEADING_WORDS or any(c.isdigit() for c in text):
        return None
    if not previous < number <= previous + MAX_NUMBER_STEP:
        return None
    return Heading(text, "numbered", number)


def build_sections(blocks: list[Block]) -> list[Section]:
    """Group raw blocks into named sections, stopping at References.

    A heading is detected on a block's first line and split off from the rest of the
    block. Text before the first heading is "Front Matter"; empty sections are dropped.
    """
    sections: list[Section] = []
    name, current, last_number = FRONT_MATTER, [], None
    for block in blocks:
        first_line, _, rest = block.text.strip().partition("\n")
        heading = detect_heading(first_line, last_number)
        if heading is None:
            body = clean(block.text)
        else:
            if heading.kind == "stop":
                break
            if current:
                sections.append(Section(name, current))
            name, current = heading.name, []
            if heading.number is not None:
                last_number = heading.number
            body = clean(rest)
        if len(body) >= MIN_BLOCK_CHARS:
            current.append(Block(body, block.page))
    if current:
        sections.append(Section(name, current))
    return sections


def choose_title(meta_title: str | None, page1_blocks: list[str], file_stem: str) -> str:
    """Pick a title: PDF metadata, else the first title-like block on page 1, else the file stem."""
    meta = (meta_title or "").strip()
    if len(meta) > 3 and not _GENERIC_TITLE.match(meta):
        return meta
    for text in page1_blocks:
        text = clean(text)
        if (
            MIN_TITLE_WORDS <= len(text.split()) <= MAX_TITLE_WORDS
            and not text.lower().startswith("arxiv")
            and "@" not in text
        ):
            return text
    return file_stem


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
