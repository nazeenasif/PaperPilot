"""Tests for ingest.build_sections() (FR-008, FR-009, research R3, R7).

Blocks hold raw extracted text (lines separated by newlines); sections hold cleaned text.
"""

from paperpilot.ingest import Block, build_sections

LONG = "This paragraph is long enough to pass the short block filter easily."


def names(sections):
    return [s.name for s in sections]


def test_text_before_first_heading_is_front_matter():
    sections = build_sections(
        [
            Block("A Study of Test Documents for Parsing", 1),
            Block("Abstract", 1),
            Block(LONG, 1),
        ]
    )
    assert names(sections) == ["Front Matter", "Abstract"]
    assert sections[0].blocks[0].text == "A Study of Test Documents for Parsing"
    assert sections[1].blocks[0].text == LONG


def test_heading_sharing_a_block_is_split_off():
    sections = build_sections([Block("1 Introduction\n" + LONG, 2)])
    assert names(sections) == ["Introduction"]
    assert sections[0].blocks == [Block(LONG, 2)]


def test_block_text_is_cleaned():
    sections = build_sections([Block("Abstract", 1), Block("We study repre-\nsentation   learning in depth.", 1)])
    assert sections[0].blocks[0].text == "We study representation learning in depth."


def test_short_blocks_dropped_but_short_headings_kept():
    sections = build_sections(
        [
            Block("Abstract", 1),  # 8 chars, kept as heading
            Block(LONG, 1),
            Block("12", 1),  # page number, dropped
            Block("Under review", 1),  # running header, dropped
            Block("1 Introduction", 1),  # 14 chars, kept as heading
            Block(LONG, 2),
        ]
    )
    assert names(sections) == ["Abstract", "Introduction"]
    assert [b.text for b in sections[0].blocks] == [LONG]
    assert [b.text for b in sections[1].blocks] == [LONG]


def test_numbered_headings_follow_sequence_from_canonical_numbers():
    sections = build_sections(
        [
            Block("2 Background", 1),
            Block(LONG, 1),
            Block("3 Model Architecture", 2),
            Block(LONG, 2),
        ]
    )
    assert names(sections) == ["Background", "Model Architecture"]


def test_references_and_everything_after_excluded():
    sections = build_sections(
        [
            Block("1 Introduction", 1),
            Block(LONG, 1),
            Block("References", 5),
            Block("[1] A. Author. A referenced paper title. Venue, 2020.", 5),
            Block("Appendix A", 6),
            Block("Appendix text that must not appear in any section at all.", 6),
        ]
    )
    assert names(sections) == ["Introduction"]
    all_text = " ".join(b.text for s in sections for b in s.blocks)
    assert "referenced paper" not in all_text
    assert "Appendix" not in all_text


def test_numbered_references_heading_sharing_a_block_stops():
    sections = build_sections(
        [Block("1 Introduction", 1), Block(LONG, 1), Block("6 References\n[1] A. Author. Title. 2020.", 4)]
    )
    assert names(sections) == ["Introduction"]


def test_no_headings_gives_single_front_matter_section():
    sections = build_sections([Block(LONG, 1), Block(LONG, 2)])
    assert names(sections) == ["Front Matter"]
    assert len(sections[0].blocks) == 2


def test_empty_sections_are_dropped():
    sections = build_sections([Block("Abstract", 1), Block("1 Introduction", 1), Block(LONG, 1)])
    assert names(sections) == ["Introduction"]


def test_no_blocks():
    assert build_sections([]) == []


def test_number_and_title_on_separate_lines_are_detected_and_split():
    sections = build_sections([Block("1\nIntroduction\n" + LONG, 1)])
    assert names(sections) == ["Introduction"]
    assert sections[0].blocks == [Block(LONG, 1)]


def test_numbered_heading_on_two_lines():
    sections = build_sections(
        [Block("2\nBackground\n", 1), Block(LONG, 1), Block("3\nModel Architecture\n", 2), Block(LONG, 2)]
    )
    assert names(sections) == ["Background", "Model Architecture"]


def test_two_line_sub_heading_does_not_start_a_section():
    sections = build_sections(
        [
            Block("2\nBackground\n", 1),
            Block(LONG, 1),
            Block("3\nModel Architecture\n", 2),
            Block(LONG, 2),
            Block("3.1\nEncoder and Decoder Stacks\n", 2),
            Block(LONG, 3),
        ]
    )
    assert names(sections) == ["Background", "Model Architecture"]


def test_unnumbered_canonical_word_in_numbered_paper_is_not_a_heading():
    # "Method" here is a table column header, not a section heading.
    sections = build_sections(
        [
            Block("1\nIntroduction\n", 1),
            Block(LONG, 1),
            Block("2\nBackground\n", 1),
            Block(LONG, 1),
            Block("3\nOur Method\n", 2),
            Block(LONG, 2),
            Block("Method\n" + LONG, 2),
            Block(LONG, 3),
        ]
    )
    assert names(sections) == ["Introduction", "Background", "Our Method"]
    assert len(sections[2].blocks) == 3


def test_unnumbered_limitations_after_numbered_conclusion_is_a_heading():
    sections = build_sections(
        [
            Block("1\nIntroduction\n", 1),
            Block(LONG, 1),
            Block("6\nConclusion\n", 9),
            Block(LONG, 9),
            Block("Limitations", 9),
            Block(LONG, 10),
        ]
    )
    assert names(sections) == ["Introduction", "Conclusion", "Limitations"]


def test_unnumbered_abstract_and_references_still_work_in_numbered_paper():
    sections = build_sections(
        [
            Block("Abstract", 1),
            Block(LONG, 1),
            Block("1 Introduction", 1),
            Block(LONG, 1),
            Block("References", 9),
            Block("[1] A. Author. A referenced paper title. Venue, 2020.", 9),
        ]
    )
    assert names(sections) == ["Abstract", "Introduction"]


def test_unnumbered_paper_keeps_unnumbered_canonical_headings():
    sections = build_sections(
        [Block("Introduction", 1), Block(LONG, 1), Block("Method", 2), Block(LONG, 2)]
    )
    assert names(sections) == ["Introduction", "Methods"]
