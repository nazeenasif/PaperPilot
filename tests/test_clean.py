"""Tests for ingest.clean() and ingest.paper_id_for()."""

from paperpilot.ingest import clean, paper_id_for


def test_joins_word_hyphenated_across_line_break():
    assert clean("repre-\nsentation") == "representation"


def test_does_not_join_hyphen_between_digits():
    assert clean("2-\n3") == "2- 3"


def test_newlines_become_spaces():
    assert clean("line one\nline two") == "line one line two"


def test_whitespace_runs_collapse():
    assert clean("a  b\t\tc \n\n d") == "a b c d"


def test_result_is_stripped():
    assert clean("  \n text \n ") == "text"


def test_empty_text_stays_empty():
    assert clean("") == ""


def test_paper_id_of_empty_bytes():
    # SHA-1 of b"" is da39a3ee5e6b4b0d3255bfef95601890afd80709.
    assert paper_id_for(b"") == "da39a3ee5e6b"


def test_paper_id_is_12_hex_chars_and_stable():
    data = b"%PDF-1.7 some paper bytes"
    first = paper_id_for(data)
    assert len(first) == 12
    assert all(c in "0123456789abcdef" for c in first)
    assert paper_id_for(data) == first


def test_different_bytes_give_different_ids():
    assert paper_id_for(b"paper one") != paper_id_for(b"paper two")
