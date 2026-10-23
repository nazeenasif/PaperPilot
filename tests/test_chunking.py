"""Tests for ingest.chunk_sections() (FR-010–FR-012, research R8, ADR-0002).

Small settings: 20-word budget, 5-word overlap, 4-word minimum. Passage text is the
words joined by single spaces. A passage's budget includes its overlap words, but a
paragraph of at most CHUNK_WORDS words is never split.
"""

import pytest

from paperpilot.config import Settings
from paperpilot.ingest import Block, Section, chunk_sections, is_table_like

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


# --- Tables (research R8): table-like blocks become their own passages. ---

TABLE_ROW = "90.6±.0 75.9±2.2 90.3±.1 85.4 RoBbase (LoRA) 0.3M 87.5±.3 95.1±.2 89.7±.7 63.4±1.2"
PROSE_WITH_NUMBERS = "We trained for 3 epochs on 8 GPUs with batch size 32 and learning rate 5e-5 using Adam"


def table(n, page=2):
    return Block(" ".join(f"{i}.{i}" for i in range(n)), page)


def test_numeric_table_row_is_table_like():
    assert is_table_like(TABLE_ROW)


def test_prose_with_a_few_numbers_is_not_table_like():
    assert not is_table_like(PROSE_WITH_NUMBERS)


def test_short_numeric_text_is_not_table_like():
    assert not is_table_like("1 2 3 4 5 6 7 8 9")  # under 10 tokens


def test_text_passages_have_kind_text():
    (passage,) = chunk(Section("Methods", [para("a", 10)]))
    assert passage.kind == "text"


def test_table_between_paragraphs_gives_three_passages_without_crossing_overlap():
    passages = chunk(Section("Results", [para("a", 8, page=1), table(12, page=2), para("b", 8, page=3)]))
    assert [p.kind for p in passages] == ["text", "table", "text"]
    assert [p.text.split() for p in passages] == [words("a", 8), table(12).text.split(), words("b", 8)]
    assert [p.page for p in passages] == [1, 2, 3]


def test_caption_before_table_stays_with_table():
    caption = Block("Table 2: Results on the test set.", 2)
    passages = chunk(Section("Results", [para("a", 8), caption, table(12), para("b", 8)]))
    assert [p.kind for p in passages] == ["text", "table", "text"]
    assert passages[1].text == caption.text + " " + table(12).text
    assert "Table" not in passages[0].text


def test_caption_after_table_stays_with_table():
    caption = Block("Table 3: Ablation results.", 2)
    passages = chunk(Section("Results", [para("a", 8), table(12), caption, para("b", 8)]))
    assert passages[1].text == table(12).text + " " + caption.text
    assert "Table" not in passages[2].text


def test_large_table_is_split_into_even_table_passages_without_overlap():
    passages = chunk(Section("Results", [table(45)]))
    assert [p.kind for p in passages] == ["table", "table", "table"]
    assert [p.word_count for p in passages] == [15, 15, 15]
    assert " ".join(p.text for p in passages) == table(45).text
