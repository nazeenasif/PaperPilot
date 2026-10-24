"""Passage geometry for citation highlights (research R4, ADR-0006). Generated PDFs only."""

from pathlib import Path

import pymupdf
import pytest

from paperpilot import ingest
from paperpilot.config import Settings
from paperpilot.ingest import align_words, build_layout, chunk_sections, parse_pdf

A4 = (595.0, 842.0)
FILLER = (
    "Researchers read many papers and often need to find one detail quickly while keyword search "
    "misses passages that use different words for the same idea so semantic search compares meanings"
)


def write_layout_pdf(path: Path, pages: list[list[tuple[str, float, float]]]) -> Path:
    """Write pages of (text, font size, box height) boxes, stacked from the top of each page."""
    doc = pymupdf.open()
    for boxes in pages:
        page = doc.new_page()
        y = 50.0
        for text, size, height in boxes:
            rect = pymupdf.Rect(50, y, 545, y + height)
            if page.insert_textbox(rect, text, fontsize=size) < 0:
                raise ValueError(f"text does not fit: {text[:40]!r}")
            y += height + 12
    doc.save(path)
    return path


def lines_of(path: Path, page_number: int, needle: str) -> list[float]:
    """Top y of each line of the block containing `needle` on a page, top to bottom."""
    with pymupdf.open(path) as doc:
        words = doc[page_number - 1].get_text("words")
    block = next(w[5] for w in words if w[4] == needle)
    return sorted({round(w[1], 1) for w in words if w[5] == block})


def covers_line(regions, page: int, top: float) -> bool:
    return any(r.page == page and abs(round(r.y0, 1) - top) < 1.0 for r in regions)


# --- parse_pdf keeps geometry ---


def test_parse_pdf_keeps_page_sizes_and_word_boxes(tmp_path, make_pdf):
    paper = parse_pdf(make_pdf(tmp_path / "paper.pdf"))
    assert paper.page_sizes == tuple([A4] * paper.page_count)
    for section in paper.sections:
        for block in section.blocks:
            assert block.words, f"block without word boxes: {block.text[:40]!r}"
            for word in block.words:
                assert 0 <= word.x0 < word.x1 <= A4[0] and 0 <= word.y0 < word.y1 <= A4[1]


def test_heading_words_are_not_kept_with_the_body(tmp_path, make_pdf):
    paper = parse_pdf(make_pdf(tmp_path / "paper.pdf"))
    intro = next(s for s in paper.sections if s.name == "Introduction")
    first = intro.blocks[0]
    assert [w.text for w in first.words][: 3] == first.text.split()[:3]


# --- align_words: cleaned words back to raw PDF words ---


def test_align_words_matches_identical_words():
    assert align_words(["a", "b", "c"], ["a", "b", "c"]) == [[0], [1], [2]]


def test_align_words_joins_a_word_hyphenated_across_lines():
    assert align_words(["the", "representation", "of"], ["the", "repre-", "sentation", "of"]) == [[0], [1, 2], [3]]


def test_align_words_handles_compound_hyphens_at_a_line_end():
    assert align_words(["state-of-theart", "results"], ["state-of-the-", "art", "results"]) == [[0, 1], [2]]


@pytest.mark.parametrize("cleaned, raw", [(["a", "x"], ["a", "b"]), (["a"], ["a", "b"]), (["a", "b"], ["a"])])
def test_align_words_gives_none_when_the_words_do_not_match(cleaned, raw):
    assert align_words(cleaned, raw) is None


# --- chunk_sections fills Passage.regions ---


def test_every_passage_has_regions_inside_its_pages(tmp_path, make_pdf):
    paper = parse_pdf(make_pdf(tmp_path / "paper.pdf"))
    passages = chunk_sections(paper.sections, paper.paper_id, paper.title, Settings())
    assert passages
    for passage in passages:
        assert passage.regions, passage.passage_id
        assert passage.exact_regions is True
        for region in passage.regions:
            assert 1 <= region.page <= paper.page_count
            assert 0 <= region.x0 < region.x1 <= A4[0] and 0 <= region.y0 < region.y1 <= A4[1]


def test_a_hyphenated_word_is_highlighted_on_both_lines(tmp_path):
    body = f"{FILLER} the repre-\nsentation stays on two lines and the passage keeps reading on for a while longer."
    path = write_layout_pdf(tmp_path / "hyphen.pdf", [[("A Paper About Hyphens And Lines", 16, 30),
                                                         ("1 Introduction", 12, 24), (body, 10, 110)]])
    paper = parse_pdf(path)
    passages = chunk_sections(paper.sections, paper.paper_id, paper.title, Settings())
    passage = next(p for p in passages if "representation" in p.text.split())
    with pymupdf.open(path) as doc:
        tops = sorted({round(w[1], 1) for w in doc[0].get_text("words") if w[4] in ("repre-", "sentation")})
    top_first, top_second = tops
    assert covers_line(passage.regions, 1, top_first)
    assert covers_line(passage.regions, 1, top_second)
    assert passage.exact_regions is True


def test_overlap_words_are_highlighted_and_split_paragraphs_cover_only_their_lines(tmp_path):
    words = [f"word{i}" for i in range(120)]
    path = write_layout_pdf(tmp_path / "long.pdf", [[("A Paper With One Long Paragraph", 16, 30),
                                                      ("1 Introduction", 12, 24), (" ".join(words), 10, 220)]])
    settings = Settings(chunk_words=40, chunk_overlap=10, min_chunk_words=5)
    paper = parse_pdf(path)
    passages = [p for p in chunk_sections(paper.sections, paper.paper_id, paper.title, settings) if "word" in p.text]
    assert len(passages) >= 3
    lines = lines_of(path, 1, "word0")
    first, last = passages[0], passages[-1]
    assert covers_line(first.regions, 1, lines[0]) and not covers_line(first.regions, 1, lines[-1])
    assert covers_line(last.regions, 1, lines[-1]) and not covers_line(last.regions, 1, lines[0])
    for earlier, later in zip(passages, passages[1:]):
        shared = {(r.page, round(r.y0, 1)) for r in earlier.regions} & {(r.page, round(r.y0, 1)) for r in later.regions}
        assert shared, "the overlap words are highlighted in both passages"


def test_a_passage_spanning_two_pages_has_regions_on_both(tmp_path):
    path = write_layout_pdf(tmp_path / "two-pages.pdf", [
        [("A Paper Whose Section Crosses A Page", 16, 30), ("1 Introduction", 12, 24), (FILLER + " first page part.", 10, 80)],
        [(FILLER + " second page part continues the same section.", 10, 80)],
    ])
    paper = parse_pdf(path)
    passages = chunk_sections(paper.sections, paper.paper_id, paper.title, Settings())
    passage = next(p for p in passages if "first" in p.text and "second" in p.text)
    assert passage.page == 1
    assert {r.page for r in passage.regions} == {1, 2}


def test_table_passages_have_regions(tmp_path):
    table = " ".join(f"{i}.{i} {i * 3} 0.{i}" for i in range(1, 12))
    path = write_layout_pdf(tmp_path / "table.pdf", [[("A Paper With A Small Results Table", 16, 30),
                                                       ("1 Results", 12, 24), (FILLER + " see the table.", 10, 70),
                                                       (table, 10, 60)]])
    paper = parse_pdf(path)
    tables = [p for p in chunk_sections(paper.sections, paper.paper_id, paper.title, Settings()) if p.kind == "table"]
    assert tables and all(t.regions for t in tables)


def test_when_alignment_fails_the_block_lines_are_used_and_marked_inexact(tmp_path, make_pdf, monkeypatch):
    monkeypatch.setattr(ingest, "align_words", lambda cleaned, raw: None)
    paper = parse_pdf(make_pdf(tmp_path / "paper.pdf"))
    passages = chunk_sections(paper.sections, paper.paper_id, paper.title, Settings())
    assert all(p.regions for p in passages)
    assert all(p.exact_regions is False for p in passages)


def test_blocks_without_word_boxes_give_no_regions():
    from paperpilot.ingest import Block, Section

    section = Section("Introduction", [Block(" ".join(["word"] * 40), 1)])
    (passage,) = chunk_sections([section], "p", "T", Settings())
    assert passage.regions == () and passage.exact_regions is False


# --- the layout file document ---


def test_build_layout_describes_pages_and_every_passage(tmp_path, make_pdf):
    settings = Settings()
    paper = parse_pdf(make_pdf(tmp_path / "paper.pdf"))
    passages = chunk_sections(paper.sections, paper.paper_id, paper.title, settings)
    layout = build_layout(paper, passages, settings)
    assert layout["version"] == 1
    assert layout["paper_id"] == paper.paper_id
    assert layout["chunking"] == {"words": 220, "overlap": 40, "min_words": 30}
    assert layout["pages"] == [{"number": n, "width": A4[0], "height": A4[1]} for n in range(1, paper.page_count + 1)]
    assert set(layout["passages"]) == {p.passage_id for p in passages}
    for regions in layout["passages"].values():
        for region in regions:
            assert set(region) == {"page", "x0", "y0", "x1", "y1"}
            assert all(region[key] == round(region[key], 2) for key in ("x0", "y0", "x1", "y1"))


# --- arXiv identifier ---


def test_parse_pdf_reads_the_arxiv_identifier_from_page_one(tmp_path):
    path = write_layout_pdf(tmp_path / "arxiv.pdf", [[("arXiv:2106.09685v2 [cs.CL] 16 Oct 2021", 9, 14),
                                                       ("A Paper Posted On The Preprint Server", 16, 30),
                                                       ("1 Introduction", 12, 24), (FILLER, 10, 70)]])
    assert parse_pdf(path).arxiv_id == "2106.09685"


def test_parse_pdf_has_no_arxiv_identifier_without_a_stamp(tmp_path, make_pdf):
    assert parse_pdf(make_pdf(tmp_path / "paper.pdf")).arxiv_id is None
