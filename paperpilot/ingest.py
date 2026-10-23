"""Read research-paper PDFs and turn them into sections and passages."""

import bisect
import hashlib
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pymupdf

from paperpilot.errors import NoTextError, PdfReadError

logger = logging.getLogger(__name__)

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


@dataclass(frozen=True)
class Span:
    """One PDF line of text, sized by its largest part; direction is (1, 0) for horizontal text."""

    size: float
    text: str
    direction: tuple[float, float]


# Optional heading number: "1", "1.", "III.", "A.".
_PREFIX = r"(?:(?P<num>\d{1,2})\.?|[IVXLC]{1,6}\.?|[A-Z]\.)\s+"
_CANONICAL = re.compile(
    rf"^(?:{_PREFIX})?(?P<word>abstract|introduction|related\s+work|background|methods?"
    r"|methodology|approach|experiments|results|discussion|limitations|conclusions?)\s*[.:]?$",
    re.IGNORECASE,
)
# A line holding only a section number: "1", "3.", "3.1", "III.", "A.".
_NUMBER_ONLY = re.compile(r"^(?:\d{1,2}(?:\.\d{1,2})*\.?|[IVXLC]{1,6}\.|[A-Z]\.)$")
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
# In a paper with numbered sections, these are the only unnumbered canonical headings kept
# (References/Bibliography always stop the paper).
UNNUMBERED_ALLOWED = {"Abstract", "Limitations"}
# Metadata titles that say nothing about the paper.
_GENERIC_TITLE = re.compile(r"^(?:untitled|microsoft word\b.*|.*\.(?:pdf|dvi|docx?|tex))$", re.IGNORECASE)
MIN_TITLE_WORDS = 3
# Consecutive title lines may differ in font size by at most this many points.
TITLE_SIZE_TOLERANCE = 0.5
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


def heading_candidate(text: str) -> tuple[str, str]:
    """Split a block into the line to test as a heading and the rest of the block.

    PDFs often put a section number and its title on separate lines ("1\\nIntroduction");
    a first line that is only a number is joined with the next line.
    """
    first, _, rest = text.strip().partition("\n")
    first = first.strip()
    if _NUMBER_ONLY.match(first) and rest.strip():
        second, _, rest = rest.strip().partition("\n")
        first = f"{first} {second.strip()}"
    return first, rest.strip()


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


def _has_numbered_headings(blocks: list[Block]) -> bool:
    """True if any heading before References carries a section number."""
    for block in blocks:
        heading = detect_heading(heading_candidate(block.text)[0], None)
        if heading is not None:
            if heading.kind == "stop":
                return False
            if heading.number is not None:
                return True
    return False


def build_sections(blocks: list[Block]) -> list[Section]:
    """Group raw blocks into named sections, stopping at References.

    A heading is detected on a block's first line and split off from the rest of the
    block. Text before the first heading is "Front Matter"; empty sections are dropped.
    If the paper numbers its sections, unnumbered canonical words (e.g. a "Method" table
    header) are not headings, except those in UNNUMBERED_ALLOWED.
    """
    numbered_paper = _has_numbered_headings(blocks)
    sections: list[Section] = []
    name, current, last_number = FRONT_MATTER, [], None
    for block in blocks:
        first_line, rest = heading_candidate(block.text)
        heading = detect_heading(first_line, last_number)
        if (
            heading is not None
            and numbered_paper
            and heading.kind == "canonical"
            and heading.number is None
            and heading.name not in UNNUMBERED_ALLOWED
        ):
            heading = None
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


def choose_title(meta_title: str | None, page1_spans: list[Span], file_stem: str) -> str:
    """Pick a title: PDF metadata, else the largest-font text on page 1, else the file stem.

    Consecutive page-1 lines within 0.5 pt of each other's size are joined. Rotated text,
    "arXiv:" stamps, candidates under 3 words and candidates containing "@" are ignored.
    """
    meta = (meta_title or "").strip()
    if len(meta) > 3 and not _GENERIC_TITLE.match(meta):
        return meta

    runs: list[tuple[float, list[str]]] = []  # (size of first line, lines)
    for span in page1_spans:
        text = span.text.strip()
        horizontal = span.direction[0] > 0 and abs(span.direction[1]) < 0.01
        if not text or not horizontal or text.lower().startswith("arxiv:"):
            continue
        if runs and abs(span.size - runs[-1][0]) <= TITLE_SIZE_TOLERANCE:
            runs[-1][1].append(text)
        else:
            runs.append((span.size, [text]))

    # Largest first; sorted() is stable, so equal sizes keep page order.
    for _, lines in sorted(runs, key=lambda run: -run[0]):
        # Newlines let clean() rejoin a word hyphenated across title lines.
        title = clean("\n".join(lines))
        if len(title.split()) >= MIN_TITLE_WORDS and "@" not in title:
            return title
    return file_stem


def merge_line(parts: list[tuple[float, str]], direction: tuple[float, float]) -> Span:
    """Merge one PDF line's (size, text) parts into a Span sized by its largest part.

    Small-caps titles alternate sizes within a line ("L" 17.2 pt, "ORA" 13.8 pt).
    """
    return Span(round(max(size for size, _ in parts), 2), "".join(text for _, text in parts), direction)


def page_spans(page: pymupdf.Page) -> list[Span]:
    """Return a page's text lines as Spans, in content order."""
    spans: list[Span] = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            parts = [(span["size"], span["text"]) for span in line["spans"]]
            if parts:
                spans.append(merge_line(parts, (float(line["dir"][0]), float(line["dir"][1]))))
    return spans


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


def parse_pdf(path: str | Path) -> ParsedPaper:
    """Read a PDF into a ParsedPaper with ordered, cleaned sections (References excluded).

    Raises PdfReadError if the file cannot be read or opened as a PDF, and NoTextError if
    it has no extractable text (for example, a scanned document).
    """
    path = Path(path)
    start = time.perf_counter()
    try:
        data = path.read_bytes()
    except OSError as error:
        raise PdfReadError(f"Cannot read {path}: {error.strerror or error}") from error
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as error:
        raise PdfReadError(f"{path.name} is not a readable PDF: {error}") from error

    with doc:
        if doc.needs_pass:
            raise PdfReadError(f"{path.name} is password-protected")
        blocks: list[Block] = []
        page1_spans = page_spans(doc[0]) if doc.page_count else []
        for number, page in enumerate(doc, start=1):
            # Text blocks only (type 0); image blocks are skipped.
            raw = [b for b in page.get_text("blocks", sort=True) if b[6] == 0 and b[4].strip()]
            ordered = order_blocks(raw, page.rect.width)
            blocks += [Block(b[4], number) for b in ordered]
        meta_title = (doc.metadata or {}).get("title")
        page_count = doc.page_count

    if not blocks:
        raise NoTextError(
            f"{path.name} has no extractable text; it may be a scanned document (OCR is not supported)"
        )
    sections = build_sections(blocks)
    if not sections:
        raise NoTextError(f"{path.name} has no usable text before its References section")
    title = choose_title(meta_title, page1_spans, path.stem)
    logger.info(
        "Parsed %s in %.2fs: %d pages, %d sections",
        path.name,
        time.perf_counter() - start,
        page_count,
        len(sections),
    )
    return ParsedPaper(paper_id_for(data), title, path.name, page_count, sections)
