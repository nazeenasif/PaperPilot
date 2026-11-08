"""Read research-paper PDFs and turn them into sections and passages."""

import bisect
import hashlib
import logging
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pymupdf

from paperpilot.config import Settings
from paperpilot.errors import NoTextError, PasswordProtectedError, PdfReadError

logger = logging.getLogger(__name__)

# A block wider than this fraction of the page is a full-width band divider.
WIDE_FRACTION = 0.6


@dataclass(frozen=True)
class Word:
    """One raw PDF word and its box in PDF points (origin top-left); line is block-relative."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    line: int


@dataclass(frozen=True)
class Region:
    """A rectangle to highlight on a 1-based page, in PDF points (origin top-left)."""

    page: int
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class Block:
    """A paragraph-like piece of text, the page it is on (1-based) and its raw word boxes."""

    text: str
    page: int
    words: tuple[Word, ...] = ()


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
    page_sizes: tuple[tuple[float, float], ...] = ()  # (width, height) in points, per page
    arxiv_id: str | None = None


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
    kind: str = "text"  # "text" or "table"
    # Where the passage's words are on the page (not stored in ChromaDB; research R4).
    regions: tuple[Region, ...] = ()
    exact_regions: bool = False  # True when every word was located (no line-box fallback)


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
# Words kept lowercase (except first) when converting ALL-CAPS labels to title case.
_SMALL_WORDS = {"a", "an", "and", "as", "at", "but", "by", "for", "in", "of", "on", "or", "the", "to", "vs", "with"}
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


def align_words(cleaned: list[str], raw: list[str]) -> list[list[int]] | None:
    """Map each cleaned word to the raw PDF word(s) it came from; None if they don't match.

    clean() only rejoins words hyphenated across line breaks ("repre-" + "sentation"), so a
    cleaned word is either one raw word or a raw word ending in "-" joined with the next one.
    """
    mapping: list[list[int]] = []
    j = 0
    for word in cleaned:
        if j < len(raw) and raw[j] == word:
            mapping.append([j])
            j += 1
        elif j + 1 < len(raw) and raw[j].endswith("-") and raw[j][:-1] + raw[j + 1] == word:
            mapping.append([j, j + 1])
            j += 2
        else:
            return None
    return mapping if j == len(raw) else None


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


def title_case(label: str) -> str:
    """Convert an ALL-CAPS label of 2+ words to title case; leave anything else unchanged.

    Single words such as "BERT" are kept, since they are usually acronyms.
    """
    words = label.split()
    if not label.isupper() or sum(any(c.isalpha() for c in w) for w in words) < 2:
        return label
    result = []
    for index, word in enumerate(words):
        word = word.lower()
        if index > 0 and word in _SMALL_WORDS:
            result.append(word)
        else:
            result.append("-".join(part[:1].upper() + part[1:] for part in word.split("-")))
    return " ".join(result)


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
    return Heading(title_case(text), "numbered", number)


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
            body, words = clean(block.text), block.words
        else:
            if heading.kind == "stop":
                break
            if current:
                sections.append(Section(name, current))
            name, current = heading.name, []
            if heading.number is not None:
                last_number = heading.number
            # The heading line(s) are raw words too: drop them so the body's words stay aligned.
            body, words = clean(rest), block.words[len(first_line.split()) :]
        if len(body) >= MIN_BLOCK_CHARS:
            current.append(Block(body, block.page, words))
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


# "arXiv:2106.09685v2 [cs.CL] ..." stamps on page 1; the version is not part of the identifier.
_ARXIV = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5})(?:v\d+)?")


def find_arxiv_id(text: str) -> str | None:
    """The arXiv identifier of an "arXiv:NNNN.NNNNN[vN]" stamp in the text, without the version."""
    match = _ARXIV.search(text)
    return match.group(1) if match else None


def _words_by_block(page: pymupdf.Page) -> dict[int, tuple[Word, ...]]:
    """A page's words grouped by PyMuPDF block number, in reading order within each block."""
    grouped: dict[int, list[tuple]] = {}
    for w in page.get_text("words"):  # (x0, y0, x1, y1, text, block_no, line_no, word_no)
        grouped.setdefault(w[5], []).append(w)
    return {
        block_no: tuple(Word(w[4], w[0], w[1], w[2], w[3], w[6]) for w in sorted(ws, key=lambda w: (w[6], w[7])))
        for block_no, ws in grouped.items()
    }


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
            raise PasswordProtectedError(f"{path.name} is password-protected")
        blocks: list[Block] = []
        page1_spans = page_spans(doc[0]) if doc.page_count else []
        arxiv_id = find_arxiv_id(doc[0].get_text()) if doc.page_count else None
        page_sizes = tuple((round(page.rect.width, 2), round(page.rect.height, 2)) for page in doc)
        for number, page in enumerate(doc, start=1):
            # Text blocks only (type 0); image blocks are skipped.
            raw = [b for b in page.get_text("blocks", sort=True) if b[6] == 0 and b[4].strip()]
            ordered = order_blocks(raw, page.rect.width)
            words = _words_by_block(page)
            blocks += [Block(b[4], number, words.get(b[5], ())) for b in ordered]
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
    return ParsedPaper(
        paper_id_for(data), title, path.name, page_count, sections, page_sizes, arxiv_id
    )


# A block is table-like if it has at least this many tokens and more than this fraction of
# them are numbers or symbols.
TABLE_MIN_TOKENS = 10
TABLE_SYMBOL_FRACTION = 0.5
_TABLE_CAPTION = re.compile(r"^Table\s+\d+\s*[:.]")
# A header row: at most this many tokens, directly before a table on the same page and column.
HEADER_MAX_TOKENS = 30
_NOT_A_HEADER = re.compile(r"^(Table|Figure|Fig\.)\s*\d")
_SENTENCE_END = re.compile(r"[A-Za-z]{5,}[.:;]|[!?](\s|$)")
_PROSE_WORDS = frozenset(
    "a an and are as at be by for from has in is it of on or that the this to was we were which with".split()
)


def _mostly_symbolic(tokens: list[str]) -> bool:
    symbolic = sum(1 for t in tokens if t[0].isdigit() or not any(c.isalpha() for c in t))
    return symbolic > TABLE_SYMBOL_FRACTION * len(tokens)


def is_table_like(text: str) -> bool:
    """True for a block that is mostly numbers or symbols, such as a flattened table."""
    tokens = text.split()
    return len(tokens) >= TABLE_MIN_TOKENS and _mostly_symbolic(tokens)


def is_table_header(text: str) -> bool:
    """True for a block that reads like a table's header row: a few short labels, not prose.

    Abbreviations such as "Avg." and "Acc." are allowed; a word of five or more letters ending in
    sentence punctuation is not, nor a line broken at a hyphen, nor everyday prose words.
    """
    tokens = text.split()
    if not 2 <= len(tokens) <= HEADER_MAX_TOKENS or _mostly_symbolic(tokens):
        return False
    if _NOT_A_HEADER.match(text) or tokens[-1].endswith("-") or _SENTENCE_END.search(text):
        return False
    return not any(t.lower() in _PROSE_WORDS for t in tokens)


def _same_column(first: Block, second: Block) -> bool:
    """True if two blocks share most of the narrower one's width; blocks without boxes count."""
    if not first.words or not second.words:
        return True
    a0, a1 = min(w.x0 for w in first.words), max(w.x1 for w in first.words)
    b0, b1 = min(w.x0 for w in second.words), max(w.x1 for w in second.words)
    return min(a1, b1) - max(a0, b0) > 0.5 * min(a1 - a0, b1 - b0)


def _units(blocks: list[Block]) -> list[tuple[str, list[Block]]]:
    """Group a section's blocks into ("text", [block]) and ("table", [caption?, rows..., caption?]).

    Consecutive table-like blocks form one table, with any header rows directly before it on
    the same page and in the same column. A "Table N:" caption directly before the table joins
    it; otherwise a caption directly after it does (unless that caption belongs to a following
    table).
    """
    tables = [is_table_like(b.text) for b in blocks]
    captions = [bool(_TABLE_CAPTION.match(b.text)) for b in blocks]
    n = len(blocks)
    for j in range(n - 2, -1, -1):  # backwards, so a header over two blocks joins whole
        if (not tables[j] and tables[j + 1] and blocks[j].page == blocks[j + 1].page
                and is_table_header(blocks[j].text) and _same_column(blocks[j], blocks[j + 1])):
            tables[j] = True
    units: list[tuple[str, list[Block]]] = []
    i = 0
    while i < n:
        group: list[Block] = []
        caption_before = captions[i] and i + 1 < n and tables[i + 1]
        if caption_before:
            group.append(blocks[i])
            i += 1
        if not tables[i]:
            units.append(("text", [blocks[i]]))
            i += 1
            continue
        while i < n and tables[i]:
            group.append(blocks[i])
            i += 1
        caption_after = i < n and captions[i] and not (i + 1 < n and tables[i + 1])
        if caption_after and not caption_before:
            group.append(blocks[i])
            i += 1
        units.append(("table", group))
    return units


def _split_table(blocks: list[Block], budget: int) -> list[list[tuple[str, tuple[Block, int]]]]:
    """Split a table's blocks into pieces of at most `budget` (word, source) pairs.

    Every piece after the first starts with the nearest header row above it, so its numbers keep
    their column names; a header of more than half the budget is not repeated. A table with no
    header is split evenly.
    """
    words: list[tuple[str, tuple[Block, int]]] = []
    headers: list[list[tuple[str, tuple[Block, int]]]] = []  # per word: the header above it
    header: list[tuple[str, tuple[Block, int]]] = []
    previous_was_header = False
    for b in blocks:
        split = [(word, (b, k)) for k, word in enumerate(b.text.split())]
        is_header = is_table_header(b.text) and not is_table_like(b.text)
        if is_header:
            header = header + split if previous_was_header else split
        words += split
        headers += [[] if is_header else header] * len(split)
        previous_was_header = is_header
    if not any(headers):
        pieces = math.ceil(len(words) / budget)
        size = math.ceil(len(words) / pieces)
        return [words[start : start + size] for start in range(0, len(words), size)]
    result = []
    start = 0
    while start < len(words):
        repeated = headers[start] if start and len(headers[start]) <= budget // 2 else []
        room = budget - len(repeated)
        result.append(repeated + words[start : start + room])
        start += room
    return result


def chunk_sections(sections: list[Section], paper_id: str, title: str, settings: Settings) -> list[Passage]:
    """Split sections into passages of about `chunk_words` words (research R8, ADR-0002).

    Whole paragraphs are packed up to the budget, which includes the overlap words carried
    from the previous passage of the same section. Only paragraphs longer than the budget
    are split. Prose with fewer than `min_chunk_words` new words is dropped at the end of a
    section or before a table. Table-like blocks (with their captions and header rows) become
    their own "table" passages, split if longer than the budget, each piece repeating the header
    row (`_split_table`); overlap never crosses them.
    Each passage records the page of its first new (non-overlap) word, and the regions of
    every word it contains, overlap included (research R4, ADR-0006).
    """
    budget, overlap = settings.chunk_words, settings.chunk_overlap
    passages: list[Passage] = []
    locate = _WordLocator()

    def emit(
        words: list[str], sources: list[tuple[Block, int]], page: int, section: str, kind: str = "text"
    ) -> tuple[list[str], list[tuple[Block, int]]]:
        """Store a passage and return the overlap words (and their sources) that start the next one."""
        n = len(passages)
        regions, exact = locate.regions(sources)
        passages.append(
            Passage(
                f"{paper_id}-{n}", paper_id, title, section, page, n, len(words), " ".join(words), kind, regions, exact
            )
        )
        if not overlap:
            return [], []
        return words[len(words) - overlap :], sources[len(sources) - overlap :]

    for section in sections:
        # Each word in `current` has a source (block, index of the word in the block's text).
        current: list[str] = []
        current_src: list[tuple[Block, int]] = []
        new_words, first_page = 0, 0
        for kind, blocks in _units(section.blocks):
            if kind == "table":
                if new_words >= settings.min_chunk_words:
                    emit(current, current_src, first_page, section.name)
                current, current_src, new_words = [], [], 0
                for piece in _split_table(blocks, budget):
                    emit([word for word, _ in piece], [source for _, source in piece], blocks[0].page,
                         section.name, "table")
                continue
            block = blocks[0]
            pending = block.text.split()
            pending_src = [(block, k) for k in range(len(pending))]
            while pending:
                if len(current) + len(pending) <= budget or (new_words == 0 and len(pending) <= budget):
                    # Fits, or a paragraph within the budget that is never split.
                    if new_words == 0:
                        first_page = block.page
                    current += pending
                    current_src += pending_src
                    new_words += len(pending)
                    pending, pending_src = [], []
                elif new_words > 0:
                    current, current_src = emit(current, current_src, first_page, section.name)
                    new_words = 0
                else:
                    # Oversized paragraph: fill this passage and carry the rest.
                    take = budget - len(current)
                    current += pending[:take]
                    current_src += pending_src[:take]
                    pending, pending_src = pending[take:], pending_src[take:]
                    current, current_src = emit(current, current_src, block.page, section.name)
        if new_words >= settings.min_chunk_words:
            emit(current, current_src, first_page, section.name)
    return passages


class _WordLocator:
    """Turns (block, word index) sources into highlight regions, one per block line.

    Each block's cleaned words are aligned to its raw PDF words once. If a block cannot be
    aligned, all of its lines are used instead and the passage is marked inexact.
    """

    def __init__(self) -> None:
        self._alignments: dict[int, tuple[Block, list[list[int]] | None]] = {}

    def _alignment(self, block: Block) -> list[list[int]] | None:
        cached = self._alignments.get(id(block))
        if cached is None or cached[0] is not block:
            cached = (block, align_words(block.text.split(), [w.text for w in block.words]))
            self._alignments[id(block)] = cached
        return cached[1]

    def regions(self, sources: list[tuple[Block, int]]) -> tuple[tuple[Region, ...], bool]:
        """Regions covering the source words, in reading order, and whether all were exact."""
        boxes: dict[tuple[int, int], list[float]] = {}
        pages: dict[tuple[int, int], int] = {}
        whole_blocks: set[int] = set()
        exact = bool(sources)

        def add(block: Block, word: Word) -> None:
            key = (id(block), word.line)
            box = boxes.get(key)
            if box is None:
                boxes[key] = [word.x0, word.y0, word.x1, word.y1]
                pages[key] = block.page
            else:
                box[0], box[1] = min(box[0], word.x0), min(box[1], word.y0)
                box[2], box[3] = max(box[2], word.x1), max(box[3], word.y1)

        for block, index in sources:
            if not block.words:
                exact = False
                continue
            mapping = self._alignment(block)
            if mapping is None:
                exact = False
                if id(block) not in whole_blocks:
                    whole_blocks.add(id(block))
                    for word in block.words:
                        add(block, word)
                continue
            for raw_index in mapping[index]:
                add(block, block.words[raw_index])
        regions = tuple(Region(pages[key], *box) for key, box in boxes.items())
        return regions, exact and bool(regions)


def build_layout(paper: ParsedPaper, passages: list[Passage], settings: Settings) -> dict:
    """The layout-file document for a paper: page sizes and each passage's regions (data-model.md)."""

    def point(value: float) -> float:
        return round(float(value), 2)

    return {
        "version": 1,
        "paper_id": paper.paper_id,
        "chunking": {
            "words": settings.chunk_words,
            "overlap": settings.chunk_overlap,
            "min_words": settings.min_chunk_words,
        },
        "pages": [
            {"number": number, "width": point(width), "height": point(height)}
            for number, (width, height) in enumerate(paper.page_sizes, start=1)
        ],
        "passages": {
            p.passage_id: [
                {"page": r.page, "x0": point(r.x0), "y0": point(r.y0), "x1": point(r.x1), "y1": point(r.y1)}
                for r in p.regions
            ]
            for p in passages
        },
    }
