"""Sentence splitting (FR-008a): abbreviations and decimals do not end a sentence. The cases are
shared with frontend/tests/sentences.test.ts, so the engine and the UI agree. No model."""

import json
from pathlib import Path

import pytest

from paperpilot import prompts

CASES = json.loads((Path(__file__).parent / "fixtures" / "sentence_cases.json").read_text(encoding="utf-8"))
SECTION = prompts.VerifiedSection if hasattr(prompts, "VerifiedSection") else None


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_sentences(case):
    assert prompts._sentences(case["text"]) == case["sentences"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_the_uncited_list_uses_the_same_sentences(case):
    assert prompts.check_citations(case["text"], passage_count=20).uncited_sentences == case["uncited"]


def test_a_tldr_with_et_al_passes_the_check():
    sections = [prompts.VerifiedSection("Data", "Data follows Houlsby et al. (2019) on GLUE [1].", [1]),
                prompts.VerifiedSection("Results", "Accuracy was 91.3 [2].", [2])]
    check = prompts.check_tldr("It follows Houlsby et al. (2019) on GLUE [1]. Accuracy was 91.3 [2].", sections)
    assert check.ok and check.problems == []
    assert check.sources == [["Data"], ["Results"]]
