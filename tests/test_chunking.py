"""Tests for ingest.chunk_sections() (FR-010–FR-012, research R8, ADR-0002).

Small settings: 20-word budget, 5-word overlap, 4-word minimum. Passage text is the
words joined by single spaces. A passage's budget includes its overlap words, but a
paragraph of at most CHUNK_WORDS words is never split.
"""

import pytest

from paperpilot.config import Settings
from paperpilot.ingest import Block, Section, chunk_sections

SETTINGS = Settings(chunk_words=20, chunk_overlap=5, min_chunk_words=4)
PID = "abcdef123456"
TITLE = "A Test Paper"


def words(prefix, n):
    return [f"{prefix}{i}" for i in range(n)]


def para(prefix, n, page=1):
    return Block(" ".join(words(prefix, n)), page)


def chunk(*sections):
    return chunk_sections(list(sections), PID, TITLE, SETTINGS)


def test_whole_paragraphs_are_packed_up_to_the_budget():
    passages = chunk(Section("Methods", [para("a", 8), para("b", 8), para("c", 8)]))
    assert [p.text.split() for p in passages] == [
        words("a", 8) + words("b", 8),
        words("b", 8)[-5:] + words("c", 8),
    ]


def test_paragraph_within_budget_is_not_split_even_after_overlap():
    passages = chunk(Section("Methods", [para("a", 18), para("b", 18)]))
    assert [p.text.split() for p in passages] == [
        words("a", 18),
        words("a", 18)[-5:] + words("b", 18),
    ]


def test_oversized_paragraph_is_hard_split():
    w = words("w", 45)
    passages = chunk(Section("Methods", [Block(" ".join(w), 1)]))
    assert [p.text.split() for p in passages] == [w[0:20], w[15:35], w[30:45]]


def test_overlap_is_not_carried_across_sections():
    passages = chunk(Section("Introduction", [para("a", 10)]), Section("Methods", [para("b", 10)]))
    assert [p.text.split() for p in passages] == [words("a", 10), words("b", 10)]
    assert [p.section for p in passages] == ["Introduction", "Methods"]


def test_no_passage_is_only_overlap():
    passages = chunk(Section("Methods", [para("a", 20)]))
    assert [p.text.split() for p in passages] == [words("a", 20)]


def test_final_leftover_under_minimum_new_words_is_dropped():
    passages = chunk(Section("Methods", [para("a", 18), para("b", 3)]))
    assert [p.text.split() for p in passages] == [words("a", 18)]


def test_tiny_section_produces_no_passage():
    assert chunk(Section("Abstract", [para("a", 3)])) == []


def test_ids_are_contiguous_after_dropped_sections():
    passages = chunk(
        Section("Introduction", [para("a", 10)]),
        Section("Background", [para("b", 3)]),
        Section("Methods", [para("c", 10)]),
    )
    assert [p.passage_id for p in passages] == [f"{PID}-0", f"{PID}-1"]
    assert [p.position for p in passages] == [0, 1]
    assert passages[1].section == "Methods"


def test_page_is_page_of_first_non_overlap_word():
    passages = chunk(Section("Methods", [para("a", 8, page=1), para("b", 8, page=2), para("c", 8, page=3)]))
    assert [p.page for p in passages] == [1, 3]


def test_passage_fields():
    (passage,) = chunk(Section("Results", [para("a", 10, page=4)]))
    assert passage.paper_id == PID
    assert passage.title == TITLE
    assert passage.section == "Results"
    assert passage.page == 4
    assert passage.word_count == 10 == len(passage.text.split())


def test_same_input_gives_identical_output():
    sections = [Section("Methods", [para("a", 8), para("b", 30), para("c", 12)])]
    assert chunk_sections(sections, PID, TITLE, SETTINGS) == chunk_sections(sections, PID, TITLE, SETTINGS)


@pytest.mark.parametrize("n", [1, 7, 19, 20, 21, 39, 40, 41, 100])
def test_every_passage_respects_size_limits(n):
    passages = chunk(Section("Methods", [para("x", n)]))
    for p in passages:
        # Overlap words plus an unsplit paragraph of at most CHUNK_WORDS words.
        assert p.word_count <= SETTINGS.chunk_words + SETTINGS.chunk_overlap
    covered = {w for p in passages for w in p.text.split()}
    if passages:
        # Words can only be lost from a final leftover under the minimum.
        assert len(set(words("x", n)) - covered) < SETTINGS.min_chunk_words
