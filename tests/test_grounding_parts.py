"""The answer validator, generalised to parts (research R1, ADR-0008).

A part (summary section, comparison cell) is valid only against the passage numbers given for
it. `ask()` keeps the special case allowed = {1..n}; its own tests stay unchanged.
"""

from paperpilot import prompts
from paperpilot.library import SearchResult
from paperpilot.prompts import NumberedPassage
from paperpilot.service import number_passages, review_reply

ANSWER = "LoRA freezes the weights [5]. It trains low-rank matrices [6, 7]. It is efficient."


def passage(number: int, passage_id: str = "p-1", text: str = "Some text [12] here.") -> NumberedPassage:
    return NumberedPassage(number, passage_id, "p", "A Paper", "Method", 3, 0.7, text)


def result(passage_id: str, rank: int = 1) -> SearchResult:
    return SearchResult(rank, 0.7, passage_id, "p", "A Paper", "Method", 3, f"text of {passage_id}")


# --- check_citations with an allowed set ---


def test_citations_outside_the_allowed_set_are_invalid():
    report = prompts.check_citations("A [5]. B [1, 8]. C [6-7].", allowed={5, 6, 7})
    assert report.valid == [5, 6, 7]
    assert report.invalid == [1, 8]


def test_uncited_sentences_are_listed_with_an_allowed_set():
    report = prompts.check_citations(ANSWER, allowed={5, 6, 7})
    assert report.uncited_sentences == ["It is efficient."]


def test_passage_count_is_the_allowed_set_one_to_n():
    text = "A [1]. B [4]. C [5]."
    assert prompts.check_citations(text, passage_count=4) == prompts.check_citations(text, allowed={1, 2, 3, 4})
    assert prompts.check_citations(text, 4) == prompts.check_citations(text, passage_count=4)  # positional, as ask() calls it


# --- review_reply with an allowed set ---


def test_review_reply_holds_back_a_part_citing_outside_its_passages():
    text, citations, warning, rejected, reason = review_reply("LoRA freezes the weights [2].", allowed={5, 6})
    assert text == prompts.NOT_FOUND and rejected == "LoRA freezes the weights [2]."
    assert citations.invalid == [2] and reason == "invalid_citations"
    assert "[2]" in warning


def test_review_reply_accepts_a_part_citing_its_own_passages():
    text, citations, warning, rejected, reason = review_reply("LoRA freezes the weights [5].", allowed={5, 6})
    assert (text, citations.valid, rejected, reason) == ("LoRA freezes the weights [5].", [5], None, None)


def test_review_reply_without_citations_and_not_found():
    assert review_reply("No citations here.", allowed={5})[4] == "no_citations"
    assert review_reply(prompts.NOT_FOUND, allowed={5})[4] == "model_not_found"


def test_review_reply_passage_count_still_works():
    assert review_reply("A [3].", 2)[4] == "invalid_citations"
    assert review_reply("A [2].", passage_count=2)[4] is None


# --- format_passages ---


def test_format_passages_is_the_answer_prompts_passage_block():
    passages = [passage(1, "p-1", "Weights <W> & B [12] are frozen."), passage(2, "p-2", "Rank r [3, 4] is small.")]
    block = prompts.format_passages(passages)
    assert prompts.build_answer_prompt("What is LoRA?", passages) == f"{block}\n\nQuestion: What is LoRA?"
    assert "[12]" not in block and "&lt;W&gt; &amp; B" in block
    assert block.startswith("Passages:\n<passage id=\"1\"")


def test_format_passages_keeps_run_wide_numbers():
    block = prompts.format_passages([passage(5, "p-5"), passage(9, "p-9")])
    assert '<passage id="5"' in block and '<passage id="9"' in block


# --- number_passages ---


def test_number_passages_numbers_from_one():
    numbered = number_passages([result("a"), result("b")])
    assert [(p.number, p.passage_id) for p in numbered] == [(1, "a"), (2, "b")]


def test_number_passages_continues_across_calls_and_keeps_first_numbers():
    seen: dict[str, NumberedPassage] = {}
    first = number_passages([result("a"), result("b")], seen)
    second = number_passages([result("c"), result("a"), result("d")], seen)
    assert [p.number for p in first] == [1, 2]
    assert [(p.number, p.passage_id) for p in second] == [(3, "c"), (1, "a"), (4, "d")]
    assert sorted(p.number for p in seen.values()) == [1, 2, 3, 4]
