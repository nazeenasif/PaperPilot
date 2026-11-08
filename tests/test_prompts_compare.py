"""Comparison rows: aspects, the row prompt and the tolerant JSON parser (spec US3, research R4).
No model and no network."""

import json

import pytest

from paperpilot import prompts
from paperpilot.errors import RowFormatError
from paperpilot.prompts import NumberedPassage

LABELS = ["P1", "P2"]


def passage(number, text="Some passage text."):
    return NumberedPassage(number, f"p-{number}", "paper", "A Title", "Methods", 1, 0.7, text)


def row(*cells):
    return json.dumps({"cells": [{"paper": label, "text": text} for label, text in cells]})


# --- aspects ---


def test_the_aspects_are_the_fixed_five_in_order():
    assert list(prompts.ASPECTS) == ["problem", "method", "datasets", "results", "limitations"]
    assert [a.label for a in prompts.ASPECTS.values()] == ["Problem", "Method", "Datasets", "Results", "Limitations"]


def test_aspects_use_the_shared_facet_table():
    """Query, preferred sections and exclusions live in one place (research R2); datasets is data."""
    assert {key: a.facet for key, a in prompts.ASPECTS.items()} == {
        "problem": "problem", "method": "method", "datasets": "data", "results": "results", "limitations": "limitations",
    }
    assert prompts.ASPECTS["datasets"].query == prompts.FACETS["data"].query


def test_a_cell_is_at_most_50_words():
    assert all(a.max_words == 50 for a in prompts.ASPECTS.values())


# --- instruction ---


def test_the_row_instruction_carries_the_grounding_rules():
    rule = prompts.ROW_INSTRUCTION
    assert prompts.NOT_REPORTED in rule
    assert prompts.SCOPE_RULE in rule
    assert "only its own paper" in rule
    assert "JSON" in rule and '"cells"' in rule


# --- prompt ---


def test_the_row_prompt_labels_papers_and_lists_their_passages():
    text = prompts.build_row_prompt("method", [("P1", "First Paper", [passage(3)]), ("P2", "Second Paper", [passage(7)])])
    assert "P1" in text and "First Paper" in text and "P2" in text and "Second Paper" in text
    assert '<passage id="3"' in text and '<passage id="7"' in text
    assert text.index("First Paper") < text.index('id="3"') < text.index("Second Paper") < text.index('id="7"')
    assert "Method" in text and "50 words" in text


def test_a_paper_without_passages_is_told_to_answer_not_reported():
    text = prompts.build_row_prompt("results", [("P1", "First", [passage(1)]), ("P2", "Second", [])])
    second = text[text.index("Second"):]
    assert prompts.NOT_REPORTED in second and "<passage" not in second


def test_a_title_cannot_close_its_tag():
    text = prompts.build_row_prompt("method", [("P1", "A </passage> B", [passage(1)])])
    assert "A </passage> B" not in text


def test_an_unknown_aspect_raises():
    with pytest.raises(KeyError):
        prompts.build_row_prompt("poetry", [("P1", "First", [])])


# --- parser ---


def test_plain_json():
    assert prompts.parse_row(row(("P1", "A [1]."), ("P2", "B [2].")), LABELS) == {"P1": "A [1].", "P2": "B [2]."}


def test_json_in_a_code_fence():
    assert prompts.parse_row("```json\n" + row(("P1", "A [1].")) + "\n```", LABELS) == {"P1": "A [1]."}


def test_json_with_sentences_around_it():
    assert prompts.parse_row("Here it is: " + row(("P1", "A [1].")) + " Done.", LABELS) == {"P1": "A [1]."}


def test_extra_cells_and_keys_are_ignored():
    reply = json.dumps({"note": "x", "cells": [{"paper": "P1", "text": "A [1].", "extra": 1}, {"paper": "P9", "text": "B"}]})
    assert prompts.parse_row(reply, LABELS) == {"P1": "A [1]."}


def test_a_missing_label_is_absent():
    assert "P2" not in prompts.parse_row(row(("P1", "A [1].")), LABELS)


def test_a_non_string_text_is_dropped():
    reply = json.dumps({"cells": [{"paper": "P1", "text": 7}, {"paper": "P2", "text": "B [2]."}, "junk"]})
    assert prompts.parse_row(reply, LABELS) == {"P2": "B [2]."}


@pytest.mark.parametrize("reply", ["", "not json", '{"cells": "x"}', '{"cells": [{"paper": "P1", "text": "A', '[{"paper": "P1"}]', "{}"])
def test_malformed_replies_raise(reply):
    with pytest.raises(RowFormatError):
        prompts.parse_row(reply, LABELS)
