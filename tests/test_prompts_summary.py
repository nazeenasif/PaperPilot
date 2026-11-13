"""Summary prompts and the TL;DR check (research R2–R3, ADR-0008). Pure and offline."""

import pytest

from paperpilot import prompts
from paperpilot.prompts import NumberedPassage, VerifiedSection, check_tldr

PROBLEM = VerifiedSection("Problem", "Fine-tuning every parameter of a large model is expensive [1].", [1])
RESULTS = VerifiedSection(
    "Results",
    "It cuts trainable parameters by about 10,000 times and GPU memory by about 3 times [4].",
    [4],
)
METHOD = VerifiedSection("Method", "The weights stay frozen; two low-rank matrices are trained [2, 3].", [2, 3])


def passage(number: int, text: str = "The pretrained weights stay frozen.") -> NumberedPassage:
    return NumberedPassage(number, f"p-{number}", "p", "A Paper", "Method", 3, 0.7, text)


# --- constants ---


def test_facets_are_the_five_sections_in_order():
    assert list(prompts.FACETS) == ["problem", "method", "data", "results", "limitations"]
    assert [f.label for f in prompts.FACETS.values()] == ["Problem", "Method", "Data", "Results", "Limitations"]
    for facet in prompts.FACETS.values():
        assert facet.query and facet.focus and facet.max_words == 80


def test_not_reported_sentence_and_version():
    assert prompts.NOT_REPORTED == "Not reported in the retrieved passages."
    assert isinstance(prompts.SUMMARY_PROMPT_VERSION, int)


# --- the scope rule (research R3, a hypothesis from F2) ---


def test_the_scope_rule_has_the_agreed_wording():
    assert prompts.SCOPE_RULE == (
        "Keep every claim's scope exactly as its source passage states it (models, datasets, conditions); "
        "never extend a result to models or tasks the passage does not name."
    )


@pytest.mark.parametrize("instruction", [prompts.SECTION_INSTRUCTION, prompts.TLDR_INSTRUCTION])
def test_section_and_tldr_instructions_carry_the_scope_rule(instruction):
    assert prompts.SCOPE_RULE in instruction


def test_the_answer_instruction_does_not_change():
    assert prompts.SCOPE_RULE not in prompts.SYSTEM_INSTRUCTION


def test_the_prompt_version_records_the_scope_rule():
    assert prompts.SUMMARY_PROMPT_VERSION >= 7


# --- builders ---


def test_section_instruction_carries_the_grounding_rules():
    rule = prompts.SECTION_INSTRUCTION
    assert prompts.NOT_REPORTED in rule
    assert "Cite every sentence" in rule and "Copy numbers" in rule
    assert "<passage>" in rule  # passage text is data, not instructions


def test_section_prompt_names_the_facet_and_lists_its_passages_with_run_wide_numbers():
    passages = [passage(5), passage(7, "Matrix B starts at zero [12].")]
    text = prompts.build_section_prompt("method", passages)
    assert prompts.format_passages(passages) in text
    assert '<passage id="5"' in text and '<passage id="7"' in text and "[12]" not in text
    assert "Method" in text and prompts.FACETS["method"].focus in text
    assert "at most 80 words" in text


def test_section_prompt_rejects_an_unknown_facet():
    with pytest.raises(KeyError):
        prompts.build_section_prompt("summary", [passage(1)])


def test_tldr_prompt_lists_only_the_given_verified_sections():
    text = prompts.build_tldr_prompt([PROBLEM, RESULTS])
    assert "Problem" in text and PROBLEM.text in text and RESULTS.text in text
    assert "Method" not in text
    assert "at most 60 words" in text and "at most 3 sentences" in text
    assert prompts.NOT_FOUND in prompts.TLDR_INSTRUCTION or prompts.NOT_REPORTED in prompts.TLDR_INSTRUCTION


def test_tldr_prompt_needs_at_least_one_section():
    with pytest.raises(ValueError):
        prompts.build_tldr_prompt([])


# --- check_tldr (research R3) ---


def test_a_faithful_tldr_passes_and_records_its_sources():
    text = ("Fine-tuning a whole large model is expensive [1]. "
            "The method cuts trainable parameters about 10,000 times and memory about 3 times [4].")
    check = check_tldr(text, [PROBLEM, RESULTS, METHOD])
    assert check.ok and not check.problems and not check.not_found
    assert check.sources == [["Problem"], ["Results"]]
    assert check.citations.valid == [1, 4] and check.citations.invalid == []


def test_a_sentence_joining_two_sections_traces_to_both():
    check = check_tldr("Freezing the weights cuts parameters 10,000 times [2, 4].", [RESULTS, METHOD])
    assert check.ok and check.sources == [["Results", "Method"]]


def test_an_uncited_sentence_fails():
    check = check_tldr("Fine-tuning is expensive [1]. The method is simple and fast.", [PROBLEM])
    assert not check.ok
    assert check.problems == ["sentence 2 has no citation"]


def test_a_citation_no_verified_section_cites_fails():
    check = check_tldr("Fine-tuning is expensive [1, 9].", [PROBLEM, RESULTS])
    assert not check.ok
    assert check.problems == ["sentence 1 cites passage 9, which no verified section cites"]
    assert check.citations.invalid == [9]


def test_a_passage_cited_only_by_a_held_back_section_fails():
    # Passage 6 belongs to a held-back section, so it is not among the verified sections' citations.
    check = check_tldr("Batching across tasks is hard [6].", [PROBLEM, RESULTS])
    assert not check.ok and "passage 6" in check.problems[0]


def test_a_number_absent_from_its_sources_fails():
    check = check_tldr("It cuts trainable parameters by about 20,000 times [4].", [RESULTS])
    assert not check.ok
    assert check.problems == ["sentence 1 states 20,000, which its sources do not contain"]


@pytest.mark.parametrize("written", ["10,000", "10000", "10 000", "10 000", "10k", "10K"])
def test_number_formats_are_normalised(written):
    check = check_tldr(f"It needs about {written} times fewer trainable parameters [4].", [RESULTS])
    assert check.ok, check.problems


def test_multiplication_signs_and_percent_keep_the_number():
    assert check_tldr("Memory drops about 3× [4].", [RESULTS]).ok
    assert check_tldr("Memory drops about 3x [4].", [RESULTS]).ok
    rag = VerifiedSection("Results", "It finds the answer for 79 percent of questions [5].", [5])
    assert check_tldr("It answers 79% of the questions [5].", [rag]).ok


def test_digits_inside_citation_markers_are_not_stated_numbers():
    # "[4]" is a citation, not a claim of "4"; the section's own markers are ignored too.
    section = VerifiedSection("Results", "Memory use drops sharply [4].", [4])
    assert check_tldr("Memory use drops sharply [4].", [section]).ok


def test_a_number_from_another_section_than_its_citation_fails():
    # 10,000 appears in Results, but the sentence cites only Problem's passage.
    check = check_tldr("Full fine-tuning costs 10,000 times more [1].", [PROBLEM, RESULTS])
    assert not check.ok and "10,000" in check.problems[0]


def test_the_not_found_sentence_is_not_reported():
    for reply in (prompts.NOT_FOUND, prompts.NOT_REPORTED):
        check = check_tldr(reply, [PROBLEM])
        assert check.not_found and not check.ok


def test_no_verified_sections_is_not_reported():
    check = check_tldr("Anything [1].", [])
    assert not check.ok and check.not_found and check.problems == ["no verified sections"]


def test_known_gap_a_non_numeric_claim_with_a_valid_citation_passes():
    """Documented limitation, not a bug to fix here: the check cannot see that [1] does not say
    "it was the first method of its kind" (the F1 pattern). See docs/known-limitations.md and
    research R3; detection belongs to the evaluation feature's faithfulness judge."""
    check = check_tldr("It was the first method of its kind [1].", [PROBLEM])
    assert check.ok
