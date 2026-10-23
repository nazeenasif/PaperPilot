"""Tests for ingest.choose_title() (FR-005, research R6).

Page 1 is given as text spans in reading order: Span(size, text, direction), where
direction is the PDF line direction (1, 0) for normal horizontal text.
"""

import pytest

from paperpilot.ingest import Span, choose_title, merge_line

H = (1.0, 0.0)  # horizontal
UP = (0.0, -1.0)  # rotated 90 degrees, like the arXiv stamp in the margin

ATTENTION_PAGE1 = [
    Span(20.0, "arXiv:1706.03762v7  [cs.CL]  2 Aug 2023", UP),
    Span(9.0, "Provided proper attribution is provided, Google hereby grants permission to", H),
    Span(9.0, "reproduce the tables and figures in this paper solely for use in journalistic or", H),
    Span(17.2, "Attention Is All", H),
    Span(17.0, "You Need", H),
    Span(10.0, "Ashish Vaswani", H),
    Span(9.0, "Google Brain", H),
]


def test_good_metadata_title_wins():
    assert choose_title("Attention Is All You Need", ATTENTION_PAGE1, "x") == "Attention Is All You Need"


def test_metadata_title_is_stripped():
    assert choose_title("  Good Title Here  ", ATTENTION_PAGE1, "x") == "Good Title Here"


@pytest.mark.parametrize(
    "meta",
    [None, "", "   ", "abc", "Untitled", "untitled", "Microsoft Word - draft.docx", "paper.pdf", "main.dvi", "notes.doc"],
)
def test_unsuitable_metadata_uses_largest_font_text(meta):
    assert choose_title(meta, ATTENTION_PAGE1, "1706.03762") == "Attention Is All You Need"


def test_rotated_stamp_larger_than_title_is_ignored():
    spans = [Span(30.0, "arXiv:2005.11401v4 [cs.CL] 12 Apr 2021", UP), Span(17.0, "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks", H)]
    assert choose_title(None, spans, "x") == "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"


def test_horizontal_arxiv_span_is_ignored():
    spans = [Span(24.0, "arXiv:2106.09685v2 [cs.CL] 16 Oct 2021", H), Span(14.0, "Low-Rank Adaptation of Large Language Models", H)]
    assert choose_title(None, spans, "x") == "Low-Rank Adaptation of Large Language Models"


def test_consecutive_lines_within_half_a_point_are_joined():
    spans = [
        Span(14.3, "BERT: Pre-training of Deep Bidirectional Transformers for", H),
        Span(14.1, "Language Understanding", H),
        Span(11.0, "Jacob Devlin Ming-Wei Chang Kenton Lee Kristina Toutanova", H),
    ]
    assert choose_title(None, spans, "x") == (
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding"
    )


def test_lines_more_than_half_a_point_apart_are_not_joined():
    spans = [Span(14.3, "Main Title Of The Paper", H), Span(13.7, "A Subtitle That Is Smaller", H)]
    assert choose_title(None, spans, "x") == "Main Title Of The Paper"


def test_only_consecutive_lines_are_joined():
    spans = [
        Span(16.0, "The Real Paper Title", H),
        Span(10.0, "Author Name", H),
        Span(16.0, "Another Large Line Later", H),
    ]
    assert choose_title(None, spans, "x") == "The Real Paper Title"


def test_whitespace_spans_do_not_break_a_title():
    spans = [Span(16.0, "Lost in the Middle:", H), Span(16.0, "  ", H), Span(16.0, "How Language Models Use Long Contexts", H)]
    assert choose_title(None, spans, "x") == "Lost in the Middle: How Language Models Use Long Contexts"


def test_candidate_under_three_words_is_ignored():
    spans = [Span(24.0, "LoRA", H), Span(14.0, "Low-Rank Adaptation of Large Language Models", H)]
    assert choose_title(None, spans, "x") == "Low-Rank Adaptation of Large Language Models"


def test_falls_back_to_file_stem():
    assert choose_title(None, [Span(20.0, "Short", H), Span(10.0, "Two words", H)], "my-paper") == "my-paper"
    assert choose_title(None, [Span(20.0, "arXiv:1234.5678 stamp text here", UP)], "my-paper") == "my-paper"
    assert choose_title(None, [], "my-paper") == "my-paper"


SMALL_CAPS_TITLE = [
    merge_line(
        [(17.2, "L"), (13.8, "O"), (17.2, "RA: L"), (13.8, "OW"), (17.2, "-R"), (13.8, "ANK"), (17.2, " A"),
         (13.8, "DAPTATION OF"), (17.2, " L"), (13.8, "ARGE"), (17.2, " L"), (13.8, "AN-")],
        H,
    ),
    merge_line([(17.2, "G"), (13.8, "UAGE"), (17.2, " M"), (13.8, "ODELS")], H),
    merge_line([(10.0, "Edward Hu"), (7.0, "*"), (10.0, " Yelong Shen Phillip Wallis Zeyuan Allen-Zhu")], H),
]


def test_merge_line_uses_largest_span_size_and_keeps_spacing():
    line = merge_line([(17.2, "L"), (13.8, "O"), (17.2, "RA: L"), (13.8, "OW")], UP)
    assert line == Span(17.2, "LORA: LOW", UP)


def test_small_caps_title_is_found_and_hyphen_rejoined():
    assert choose_title(None, SMALL_CAPS_TITLE, "2106.09685") == "LORA: LOW-RANK ADAPTATION OF LARGE LANGUAGE MODELS"


def test_candidate_with_at_sign_is_rejected():
    spans = [
        Span(12.0, "Jane Doe and John Roe jane@example.com", H),
        Span(11.0, "A Real Paper Title", H),
    ]
    assert choose_title(None, spans, "x") == "A Real Paper Title"
