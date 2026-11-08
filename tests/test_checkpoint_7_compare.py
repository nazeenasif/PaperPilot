"""Checkpoint 7's comparison checks, as pure functions. No model and no network."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from checkpoint_7_summaries import PARTS, cell_rows, foreign_citations, row_token_rows  # noqa: E402


def cell(name, state="verified", text="A claim [1].", valid=(1,), invalid=()):
    return {"part": name, "state": state, "text": text, "reason": None,
            "citations": {"valid": list(valid), "invalid": list(invalid), "uncited_sentences": []}}


def comparison(*rows):
    return {
        "papers": [{"paper_id": "a", "title": "Paper A", "label": "P1"}, {"paper_id": "b", "title": "Paper B", "label": "P2"}],
        "passages": [
            {"number": 1, "paper_id": "a", "title": "Paper A", "section": "Methods", "page": 2, "text": "from a"},
            {"number": 2, "paper_id": "b", "title": "Paper B", "section": "Methods", "page": 3, "text": "from b"},
        ],
        "rows": list(rows),
    }


def row(aspect, *cells, state="ok", reason=None, tokens=None):
    return {"aspect": aspect, "state": state, "reason": reason, "cells": list(cells), "tokens": tokens or {}}


def test_a_cell_citing_its_own_paper_is_fine():
    found = comparison(row("method", cell("method:a", valid=[1]), cell("method:b", valid=[2])))
    assert foreign_citations(found) == []


def test_a_verified_cell_citing_another_paper_is_reported():
    found = comparison(row("method", cell("method:a", valid=[2])))
    assert foreign_citations(found) == [("method:a", 2)]


def test_cells_that_are_not_shown_are_not_counted():
    found = comparison(row("method", cell("method:a", state="held_back", valid=[2])))
    assert foreign_citations(found) == []


def test_claims_name_the_paper_and_its_passages():
    rows = cell_rows("BERT vs RAG", comparison(row("method", cell("method:a", text="One [1]. Two [1]."))))
    assert [(source, part, sentence) for source, part, sentence, _ in rows] == [
        ("BERT vs RAG", "method · Paper A", "One [1]."), ("BERT vs RAG", "method · Paper A", "Two [1]."),
    ]
    assert rows[0][3][0]["section"] == "Methods"


def test_token_rows_cover_every_row_including_failed_ones():
    rows = row_token_rows(comparison(
        row("method", tokens={"input": 900, "output": 1200, "reasoning": 1000}),
        row("results", state="failed", reason="malformed", tokens={"input": 900, "output": 500, "reasoning": 480}),
        row("limitations", state="not_started", reason="daily_limit"),
    ))
    assert rows == [
        ("Method", "ok", 900, 1200, 1000, 200),
        ("Results", "failed (malformed)", 900, 500, 480, 20),
        ("Limitations", "not_started (daily_limit)", None, None, None, None),
    ]


def test_the_plan_for_the_comparison_parts():
    assert (PARTS["compare"].plan, PARTS["not-reported"].plan, PARTS["states"].plan) == (3, 1, 0)
