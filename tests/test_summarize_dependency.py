"""Which sections a TL;DR was built from, and "built without <section>" after a section is
regenerated, until the TL;DR is regenerated too. Scripted model only; no network."""

import pytest

from paperpilot import library, llm, prompts, service
from paperpilot.errors import LLMError
from test_summarize import PromptReadingLLM

FACETS = ["problem", "method", "data", "results", "limitations"]


@pytest.fixture
def model(summary_env, monkeypatch):
    fake = PromptReadingLLM()
    monkeypatch.setattr(llm, "generate", fake)
    return fake


def fail_method_once(monkeypatch):
    fake = PromptReadingLLM()

    def generate(system, prompt, on_retry=None, task="answer"):
        if "Section: Method." in prompt:
            raise LLMError("cut off", reason="cut_off")
        return fake(system, prompt, on_retry, task)

    monkeypatch.setattr(llm, "generate", generate)


def test_a_tldr_records_the_sections_it_was_built_from(summary_env, model):
    tldr = service.summarize(summary_env.paper_id).tldr
    assert tldr.built_from == FACETS and tldr.built_without == []


def test_a_section_that_failed_is_recorded_as_built_without(summary_env, monkeypatch):
    fail_method_once(monkeypatch)
    tldr = service.summarize(summary_env.paper_id).tldr
    assert tldr.built_from == ["problem", "data", "results", "limitations"]
    assert tldr.built_without == ["method"]


def test_a_section_not_reported_is_not_a_missing_ingredient(summary_env, monkeypatch):
    monkeypatch.setattr(llm, "generate", PromptReadingLLM({"limitations": prompts.NOT_REPORTED}))
    tldr = service.summarize(summary_env.paper_id).tldr
    assert tldr.built_from == FACETS[:4] and tldr.built_without == []


def test_regenerating_a_section_marks_the_tldr_built_without_it(summary_env, model):
    first = service.summarize(summary_env.paper_id)
    calls = len(model.calls)
    retried = service.summarize(summary_env.paper_id, retry_parts=["method"])
    assert len(model.calls) == calls + 1
    assert retried.tldr.text == first.tldr.text
    assert retried.tldr.built_from == ["problem", "data", "results", "limitations"]
    assert retried.tldr.built_without == ["method"]
    assert service.saved_summary(summary_env.paper_id).tldr.built_without == ["method"]


def test_regenerating_the_tldr_clears_the_mark(summary_env, monkeypatch):
    fail_method_once(monkeypatch)
    service.summarize(summary_env.paper_id)
    model = PromptReadingLLM()
    monkeypatch.setattr(llm, "generate", model)
    service.summarize(summary_env.paper_id, retry_parts=["method"])
    assert service.saved_summary(summary_env.paper_id).tldr.built_without == ["method"]
    calls = len(model.calls)
    rewritten = service.summarize(summary_env.paper_id, retry_parts=["tldr"])
    assert len(model.calls) == calls + 1 and model.calls[-1][0] == prompts.TLDR_INSTRUCTION
    assert '<section name="Method">' in model.calls[-1][1]
    assert rewritten.tldr.built_from == FACETS and rewritten.tldr.built_without == []
    assert rewritten.sections[1].state == "verified"


def test_a_section_and_the_tldr_can_be_regenerated_together(summary_env, model):
    service.summarize(summary_env.paper_id)
    calls = len(model.calls)
    both = service.summarize(summary_env.paper_id, retry_parts=["method", "tldr"])
    assert len(model.calls) == calls + 2
    assert both.tldr.built_without == []


def test_a_summary_saved_before_this_field_gets_its_sections_from_their_states(summary_env, monkeypatch):
    """Rows saved earlier have no built_from; a retry was not offered then, so the sections
    verified now are the ones the TL;DR saw."""
    fail_method_once(monkeypatch)
    summary = service.summarize(summary_env.paper_id)
    data = service.summary_to_dict(summary)
    del data["tldr"]["built_from"], data["tldr"]["built_without"]
    library.save_result(library.result_key("summary", [summary.paper_id]), data, summary.model, summary.prompt_version)
    tldr = service.saved_summary(summary_env.paper_id).tldr
    assert tldr.built_from == ["problem", "data", "results", "limitations"]
    assert tldr.built_without == ["method"]


def test_no_tldr_means_nothing_to_mark(summary_env, monkeypatch):
    monkeypatch.setattr(llm, "generate", PromptReadingLLM({f: "No citation." for f in FACETS}))
    tldr = service.summarize(summary_env.paper_id).tldr
    assert (tldr.state, tldr.built_from, tldr.built_without) == ("not_reported", [], [])

