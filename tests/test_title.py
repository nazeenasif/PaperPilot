"""Tests for ingest.choose_title() (FR-005, research R6)."""

import pytest

from paperpilot.ingest import choose_title

PAGE1 = [
    "arXiv:1706.03762v7 [cs.CL] 2 Aug 2023",
    "Attention Is All You Need",
    "Ashish Vaswani Google Brain avaswani@google.com",
]


def test_good_metadata_title_wins():
    assert choose_title("Attention Is All You Need", PAGE1, "1706.03762") == "Attention Is All You Need"


def test_metadata_title_is_stripped():
    assert choose_title("  Good Title Here  ", PAGE1, "x") == "Good Title Here"


@pytest.mark.parametrize(
    "meta",
    [None, "", "   ", "abc", "Untitled", "untitled", "Microsoft Word - draft.docx", "paper.pdf", "main.dvi", "notes.doc"],
)
def test_unsuitable_metadata_falls_back_to_page_1(meta):
    assert choose_title(meta, PAGE1, "1706.03762") == "Attention Is All You Need"


def test_page_1_skips_short_long_arxiv_and_email_blocks():
    page1 = [
        "Short title",  # 2 words: too short
        " ".join(["word"] * 31),  # 31 words: too long
        "arXiv preprint, under review at a conference",
        "Jane Doe and John Roe jane@example.com university",
        "Learning to Parse Research Papers Well",
    ]
    assert choose_title(None, page1, "stem") == "Learning to Parse Research Papers Well"


def test_falls_back_to_file_stem():
    assert choose_title(None, ["12", "Short"], "my-paper") == "my-paper"
    assert choose_title(None, [], "my-paper") == "my-paper"
