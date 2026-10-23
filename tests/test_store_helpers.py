"""Tests for store.distance_to_score() and store.build_where() (research R10)."""

import pytest

from paperpilot.store import build_where, distance_to_score


@pytest.mark.parametrize(
    ("distance", "score"),
    [(0.0, 1.0), (0.2, 0.8), (1.0, 0.0), (1.5, 0.0), (2.0, 0.0), (0.1234, 0.877)],
)
def test_distance_to_score(distance, score):
    assert distance_to_score(distance) == score


def test_no_filter_when_no_paper_ids():
    assert build_where(None) is None
    assert build_where([]) is None


def test_filter_uses_in_list():
    assert build_where(["a"]) == {"paper_id": {"$in": ["a"]}}
    assert build_where(["a", "b"]) == {"paper_id": {"$in": ["a", "b"]}}
