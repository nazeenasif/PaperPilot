"""Tests for ingest.order_blocks() band-based column ordering (research R2)."""

from paperpilot.ingest import order_blocks

PAGE_WIDTH = 600.0  # midpoint 300; "wide" means wider than 360


def texts(blocks):
    return [b[4] for b in blocks]


def test_two_columns_left_then_right():
    blocks = [
        (320, 100, 550, 200, "R1"),
        (50, 220, 280, 300, "L2"),
        (50, 100, 280, 200, "L1"),
        (320, 220, 550, 300, "R2"),
    ]
    assert texts(order_blocks(blocks, PAGE_WIDTH)) == ["L1", "L2", "R1", "R2"]


def test_full_width_title_at_top_comes_first():
    blocks = [
        (320, 100, 550, 200, "R1"),
        (50, 100, 280, 200, "L1"),
        (50, 40, 550, 80, "TITLE"),
        (320, 220, 550, 300, "R2"),
        (50, 220, 280, 300, "L2"),
    ]
    assert texts(order_blocks(blocks, PAGE_WIDTH)) == ["TITLE", "L1", "L2", "R1", "R2"]


def test_full_width_caption_mid_page_splits_into_bands():
    blocks = [
        (50, 400, 280, 500, "L-below"),
        (320, 100, 550, 300, "R-above"),
        (50, 320, 550, 350, "CAPTION"),
        (320, 400, 550, 500, "R-below"),
        (50, 100, 280, 300, "L-above"),
    ]
    assert texts(order_blocks(blocks, PAGE_WIDTH)) == [
        "L-above",
        "R-above",
        "CAPTION",
        "L-below",
        "R-below",
    ]


def test_single_column_page_keeps_top_to_bottom_order():
    blocks = [
        (50, 300, 550, 350, "third"),
        (50, 100, 550, 150, "first"),
        (50, 200, 550, 250, "second"),
    ]
    assert texts(order_blocks(blocks, PAGE_WIDTH)) == ["first", "second", "third"]


def test_extra_tuple_fields_are_preserved():
    # PyMuPDF blocks are (x0, y0, x1, y1, text, block_no, block_type).
    blocks = [(320, 100, 550, 200, "R", 1, 0), (50, 100, 280, 200, "L", 0, 0)]
    assert order_blocks(blocks, PAGE_WIDTH) == [blocks[1], blocks[0]]


def test_empty_page():
    assert order_blocks([], PAGE_WIDTH) == []
