"""Tests for ingest.chunk_sections() (FR-010–FR-012, research R8, ADR-0002).

Small settings: 20-word budget, 5-word overlap, 4-word minimum. Passage text is the
words joined by single spaces. A passage's budget includes its overlap words, but a
paragraph of at most CHUNK_WORDS words is never split.
"""

import pytest

from paperpilot.config import Settings
from paperpilot.ingest import Block, Section, Word, chunk_sections, is_table_header, is_table_like

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


WIDE = Settings(chunk_words=60, chunk_overlap=5, min_chunk_words=4)


def row(label, page=2):
    return Block(f"{label} " + " ".join(f"{i}.{i}" for i in range(10)), page)


def test_consecutive_table_blocks_and_caption_become_one_table_passage():
    caption = Block("Table 1: Results on three tasks.", 2)
    blocks = [para("a", 8), caption, row("r1"), row("r2"), row("r3"), para("b", 8)]
    passages = chunk_sections([Section("Results", blocks)], PID, TITLE, WIDE)
    assert [p.kind for p in passages] == ["text", "table", "text"]
    assert passages[1].text == " ".join(b.text for b in [caption, row("r1"), row("r2"), row("r3")])


def test_merged_table_longer_than_budget_is_split_evenly():
    passages = chunk(Section("Results", [row("r1"), row("r2"), row("r3")]))  # 33 tokens, budget 20
    assert [p.kind for p in passages] == ["table", "table"]
    assert [p.word_count for p in passages] == [17, 16]


def test_caption_between_tables_starts_a_new_table():
    caption = Block("Table 2: Second table.", 2)
    passages = chunk_sections([Section("Results", [row("r1"), caption, row("r2")])], PID, TITLE, WIDE)
    assert [p.kind for p in passages] == ["table", "table"]
    assert passages[1].text.startswith("Table 2:")


# --- table header rows (real cases) ---

LORA_TABLE_5_HEADER = "Weight Type Wq Wk Wv Wo Wq, Wk Wq, Wv Wq, Wk, Wv, Wo Rank r 8 8 8 8 4 4 2"
LORA_TABLE_5 = "WikiSQL (±0.5%) 70.4 70.0 73.0 73.2 71.4 73.7 73.7 MultiNLI (±0.1%) 91.0 90.8 91.0 91.3 91.3 91.3 91.7"
LORA_TABLE_5_CAPTION = "Table 5: Validation accuracy on WikiSQL and MultiNLI after applying LoRA to different types of attention weights."
ATTENTION_HEADER = "N dmodel dff h dk dv Pdrop ϵls train PPL BLEU params steps (dev) (dev) ×106"
ATTENTION_ROWS = "base 6 512 2048 8 64 64 0.1 0.1 100K 4.92 25.8 65"


@pytest.mark.parametrize("text", [
    LORA_TABLE_5_HEADER,
    ATTENTION_HEADER,
    "Parameters MNLI SST-2 MRPC CoLA QNLI QQP RTE STS-B Avg.",
    "Model&Method # Trainable WikiSQL MNLI-m SAMSum Parameters Acc. (%) Acc. (%) R1/R2/RL",
    "Model NQ TQA WQ CT Jeopardy-QGen MSMarco FVR-3 FVR-2 Exact Match B-1 QB-1 R-L B-1 Label Accuracy",
    "#L #H #A LM (ppl) MNLI-m MRPC SST-2",
    "System Dev Test EM F1 EM F1",
    "Model & Method # Trainable",
])
def test_real_header_rows_are_recognised(text):
    assert is_table_header(text)


@pytest.mark.parametrize("text", [
    "Figure 11 presents retriever recall and open-",  # a line of prose
    "8See (10) in https://gluebenchmark.com/faq.",  # a footnote
    "We turn our attention to the effect of rank r on model performance.",
    "Table 5: Ratio of distinct to total tri-grams for generation tasks.",  # a caption
    "Figure 2: Accuracy on the three datasets",
    "(B) 16 5.16 25.1 58 32 5.01 25.4 60",  # a numeric row
    "BART 15.1 19.7 38.2 41.6 64.0 81.1",
    "Results",  # a single word
    " ".join(["Column"] * 31),  # too long
])
def test_other_short_blocks_are_not_header_rows(text):
    assert not is_table_header(text)


def boxed(text, x0, x1, page=2):
    """A block whose words all sit between x0 and x1."""
    return Block(text, page, tuple(Word(t, x0, 100, x1, 110, 0) for t in text.split()))


def test_lora_table_5_keeps_its_header_row():
    passages = chunk(Section("Understanding", [
        para("a", 8), Block(LORA_TABLE_5_HEADER, 10), Block(LORA_TABLE_5, 10), Block(LORA_TABLE_5_CAPTION, 10), para("b", 8),
    ]))
    tables = [p for p in passages if p.kind == "table"]
    joined = " ".join(p.text for p in tables)
    assert joined.startswith("Weight Type Wq Wk Wv Wo") and "91.7" in joined and joined.endswith("attention weights.")
    assert "Weight" not in passages[0].text


def test_attention_table_keeps_its_header_row():
    passages = chunk(Section("Results", [para("a", 8), Block(ATTENTION_HEADER, 9), Block(ATTENTION_ROWS, 9)]))
    assert " ".join(p.text for p in passages if p.kind == "table") == ATTENTION_HEADER + " " + ATTENTION_ROWS
    assert "dmodel" not in passages[0].text


def test_a_header_spread_over_two_blocks_stays_together():
    first, second = "Model & Method # Trainable", "Parameters MNLI SST-2 MRPC CoLA QNLI QQP RTE STS-B Avg."
    rows = "RoBbase 125.0M 87.6 94.8 90.2 63.6 92.8 91.9 78.7 91.2 86.4"
    passages = chunk(Section("Results", [para("a", 8), Block(first, 6), Block(second, 6), Block(rows, 6)]))
    assert " ".join(p.text for p in passages if p.kind == "table") == f"{first} {second} {rows}"


def test_a_caption_before_a_header_row_joins_the_table_too():
    caption = "Table 4: Scores on the test set."
    passages = chunk(Section("Results", [para("a", 8), Block(caption, 9), Block(ATTENTION_HEADER, 9), Block(ATTENTION_ROWS, 9)]))
    assert " ".join(p.text for p in passages if p.kind == "table") == f"{caption} {ATTENTION_HEADER} {ATTENTION_ROWS}"


def test_a_short_block_in_the_other_column_is_not_attached():
    passages = chunk(Section("Results", [
        para("a", 8), boxed(ATTENTION_HEADER, 50, 290), boxed(ATTENTION_ROWS, 310, 550), para("b", 8),
    ]))
    assert ATTENTION_ROWS == " ".join(p.text for p in passages if p.kind == "table")
    assert any("dmodel" in p.text for p in passages if p.kind == "text")


def test_a_narrow_header_above_a_wide_table_in_the_same_column_is_attached():
    passages = chunk(Section("Results", [para("a", 8), boxed(ATTENTION_HEADER, 100, 300), boxed(ATTENTION_ROWS, 50, 550)]))
    assert " ".join(p.text for p in passages if p.kind == "table") == ATTENTION_HEADER + " " + ATTENTION_ROWS


def test_a_short_block_on_the_previous_page_is_not_attached():
    passages = chunk(Section("Results", [para("a", 8), Block(ATTENTION_HEADER, 8), Block(ATTENTION_ROWS, 9)]))
    assert " ".join(p.text for p in passages if p.kind == "table") == ATTENTION_ROWS


def test_a_header_like_block_with_no_table_after_it_stays_text():
    passages = chunk(Section("Results", [Block(ATTENTION_HEADER, 9), para("b", 8)]))
    assert {p.kind for p in passages} == {"text"} and "dmodel" in passages[0].text


# --- a split table repeats its header row (real case: LoRA Table 2, p. 6) ---

LORA_TABLE_2_HEADER = "Parameters MNLI SST-2 MRPC CoLA QNLI QQP RTE STS-B Avg."
LORA_TABLE_2_ROWS = [
    "RoBbase (FT)* 125.0M 87.6 94.8 90.2 63.6 92.8 91.9 78.7 91.2 86.4",
    "RoBlarge (AdptH)† 0.8M 90.3±.3 96.3±.5 87.7±1.7 66.3±2.0 94.7±.2 91.5±.1 72.9±2.9 91.5±.5 86.4",
    "RoBlarge (LoRA)† 0.8M 90.6±.2 96.2±.5 90.2±1.0 68.2±1.9 94.8±.3 91.6±.2 85.2±1.1 92.3±.5 88.6",
    "DeBXXL (FT)* 1500.0M 91.8 97.2 92.0 72.0 96.0 92.7 93.9 92.9 91.1",
    "DeBXXL (LoRA) 4.7M 91.9±.2 96.9±.2 92.6±.6 72.4±1.1 96.0±.1 92.9±.1 94.9±.4 93.0±.2 91.3",
]
HEADER_WORDS = LORA_TABLE_2_HEADER.split()


def table_2(*before):
    section = Section("Empirical Experiments", [para("a", 8), *before, Block(LORA_TABLE_2_HEADER, 6),
                                                *(Block(row, 6) for row in LORA_TABLE_2_ROWS)])
    return [p for p in chunk(section) if p.kind == "table"]


def test_every_passage_of_a_split_table_starts_with_its_header_row():
    tables = table_2()
    assert len(tables) > 1
    assert all(p.text.split()[: len(HEADER_WORDS)] == HEADER_WORDS for p in tables)


def test_a_split_table_loses_no_row_words_and_repeats_none():
    rows = " ".join(LORA_TABLE_2_ROWS).split()
    assert [w for p in table_2() for w in p.text.split()[len(HEADER_WORDS):]] == rows


def test_a_split_table_stays_within_the_budget_and_counts_the_repeated_words():
    """Only a merged short tail can pass the budget, by fewer than the minimum's words."""
    limit = SETTINGS.chunk_words + SETTINGS.min_chunk_words
    assert all(p.word_count == len(p.text.split()) < limit for p in table_2())


def test_a_repeated_header_comes_after_the_caption_only_in_the_first_piece():
    caption = "Table 2: GLUE results."
    tables = table_2(Block(caption, 6))
    assert tables[0].text.startswith(f"{caption} {LORA_TABLE_2_HEADER}")
    assert all(p.text.startswith(LORA_TABLE_2_HEADER) for p in tables[1:])


def test_a_split_table_uses_the_header_nearest_above_it():
    second = "System Dev Test EM F1 EM F1"
    section = Section("Results", [
        Block(LORA_TABLE_2_HEADER, 6), Block(" ".join(LORA_TABLE_2_ROWS[:2]), 6),
        Block(second, 6), Block(" ".join(LORA_TABLE_2_ROWS[2:]), 6),
    ])
    tables = [p for p in chunk(section) if p.kind == "table"]
    assert tables[0].text.startswith(LORA_TABLE_2_HEADER) and tables[-1].text.startswith(second)


def test_a_header_too_long_to_repeat_is_not_repeated():
    header = "Model NQ TQA WQ CT Jeopardy-QGen MSMarco FVR-3 FVR-2 Exact Match"  # over half of 20 words
    section = Section("Results", [Block(header, 6), *(Block(row, 6) for row in LORA_TABLE_2_ROWS)])
    tables = [p for p in chunk(section) if p.kind == "table"]
    assert tables[0].text.startswith(header) and not any(p.text.startswith(header) for p in tables[1:])
    assert [w for p in tables for w in p.text.split()] == f"{header} {' '.join(LORA_TABLE_2_ROWS)}".split()


def test_a_short_table_with_a_header_is_one_passage_with_one_header():
    rows = " ".join(ATTENTION_ROWS.split()[:10])
    tables = [p for p in chunk(Section("Results", [Block("System Dev Test EM F1 EM F1", 9), Block(rows, 9)])) if p.kind == "table"]
    assert [p.text for p in tables] == [f"System Dev Test EM F1 EM F1 {rows}"]


def test_a_repeated_header_is_highlighted_where_it_is_on_the_page():
    header = boxed(LORA_TABLE_2_HEADER, 50, 550, page=6)
    rows = [boxed(row, 50, 550, page=6) for row in LORA_TABLE_2_ROWS]
    tables = [p for p in chunk(Section("Results", [header, *rows])) if p.kind == "table"]
    assert all(p.regions and p.exact_regions for p in tables)


# --- a short tail joins the previous piece (real case: LoRA Table 2's caption end, p. 6) ---

LORA_TABLE_2_CAPTION_END = "Table 2: Higher is better for all metrics."
TAIL_SETTINGS = Settings(chunk_words=30, chunk_overlap=5, min_chunk_words=10)


def rows_of(count):
    """Numeric row words filling exactly `count` words, so the caption end falls where a test needs."""
    return Block(" ".join(f"9{i}.{i % 10}" for i in range(count)), 6)


def table_with_tail(row_words, tail=LORA_TABLE_2_CAPTION_END):
    section = Section("Empirical Experiments", [Block(LORA_TABLE_2_HEADER, 6), rows_of(row_words), Block(tail, 6)])
    return [p for p in chunk_sections([section], PID, TITLE, TAIL_SETTINGS) if p.kind == "table"]


def test_lora_table_2s_caption_end_joins_the_rows_instead_of_standing_alone():
    """The header takes 10 words of the first 30 and 10 of each later piece, so 20 rows fill the first
    piece and the 8 words of caption would be a piece of their own, under the minimum of 10."""
    tables = table_with_tail(20)
    assert len(tables) == 1
    assert tables[0].text.startswith(LORA_TABLE_2_HEADER) and tables[0].text.endswith(LORA_TABLE_2_CAPTION_END)


def test_a_merged_tail_does_not_repeat_the_header():
    assert table_with_tail(20)[0].text.count("MNLI") == 1


def test_a_merged_tail_loses_no_words_and_counts_them():
    [table] = table_with_tail(20)
    assert table.word_count == len(table.text.split()) == len(HEADER_WORDS) + 20 + 8


def test_a_tail_of_at_least_the_minimum_stays_its_own_piece():
    tail = "Table 2: Higher is better for all metrics, as reported in prior works."
    tables = table_with_tail(20, tail)
    assert len(tables) == 2 and tables[1].text == f"{LORA_TABLE_2_HEADER} {tail}"


def test_the_repeated_header_does_not_count_towards_the_minimum():
    """8 tail words plus the 10 repeated header words are 18, over the minimum, but only 8 are new."""
    assert len(table_with_tail(20)) == 1


def test_only_the_last_piece_of_a_long_table_can_merge():
    tables = table_with_tail(20 + 20 + 20)
    assert len(tables) == 3
    assert all(p.text.startswith(LORA_TABLE_2_HEADER) for p in tables)
    assert tables[-1].text.endswith(LORA_TABLE_2_CAPTION_END)


def test_a_table_without_a_header_merges_its_short_tail_too():
    section = Section("Results", [rows_of(61)])
    tables = [p for p in chunk_sections([section], PID, TITLE, Settings(chunk_words=30, chunk_overlap=5, min_chunk_words=10)) if p.kind == "table"]
    assert all(p.word_count >= 10 for p in tables) and sum(p.word_count for p in tables) == 61


def test_a_table_that_is_all_one_short_piece_stays():
    tables = table_with_tail(1, tail="Table 9: A note.")
    assert len(tables) <= 1
