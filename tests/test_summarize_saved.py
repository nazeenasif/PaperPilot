"""Saved summaries: reopen at no cost, stale results, regenerate, retry parts (spec US2,
FR-016-FR-020; research R6, R8; ADR-0009). Scripted model only."""

import dataclasses

import pytest

from paperpilot import library, llm, prompts, service
from test_summarize import PromptReadingLLM


@pytest.fixture
def model(summary_env, monkeypatch):
    fake = PromptReadingLLM()
    monkeypatch.setattr(llm, "generate", fake)
    return fake


def resave(summary: service.Summary) -> None:
    """Save a modified summary as if a run had produced it."""
    library.save_result(library.result_key("summary", [summary.paper_id]), service.summary_to_dict(summary),
                        model=summary.model, prompt_version=summary.prompt_version)


def test_a_saved_summary_reopens_with_zero_requests(summary_env, model):
    first = service.summarize(summary_env.paper_id)
    calls, counts = len(model.calls), llm.request_counts()
    again = service.summarize(summary_env.paper_id)
    assert len(model.calls) == calls and llm.request_counts() == counts
    assert again == first and again.status == "current"


def test_saved_summary_returns_it_without_generating(summary_env, model):
    assert service.saved_summary(summary_env.paper_id) is None
    first = service.summarize(summary_env.paper_id)
    calls = len(model.calls)
    assert service.saved_summary(summary_env.paper_id) == first
    assert len(model.calls) == calls


def test_a_summary_from_another_model_is_stale_and_not_regenerated_silently(summary_env, model, monkeypatch):
    service.summarize(summary_env.paper_id)
    monkeypatch.setenv("LLM_MODEL", "other/model:free")
    calls = len(model.calls)
    stale = service.saved_summary(summary_env.paper_id)
    assert (stale.status, stale.stale_reason) == ("stale", "model_changed")
    reopened = service.summarize(summary_env.paper_id)  # analysis I1: return it marked stale
    assert (reopened.status, reopened.stale_reason) == ("stale", "model_changed")
    assert len(model.calls) == calls


def test_regenerate_writes_a_new_summary(summary_env, model, monkeypatch):
    service.summarize(summary_env.paper_id)
    monkeypatch.setattr(llm, "generate", PromptReadingLLM({"results": "Training is faster [1]."}))
    new = service.summarize(summary_env.paper_id, regenerate=True)
    assert new.sections[3].text == "Training is faster [1]." or new.sections[3].state == "held_back"
    assert service.saved_summary(summary_env.paper_id) == new


def test_a_regeneration_that_fails_midway_keeps_the_saved_summary(summary_env, model, monkeypatch):
    first = service.summarize(summary_env.paper_id)

    class Exploding(PromptReadingLLM):
        def __call__(self, system, prompt, on_retry=None, task="answer"):
            if len(self.calls) == 2:
                raise RuntimeError("process died")
            return super().__call__(system, prompt, on_retry, task)

    monkeypatch.setattr(llm, "generate", Exploding())
    with pytest.raises(RuntimeError):
        service.summarize(summary_env.paper_id, regenerate=True)
    assert service.saved_summary(summary_env.paper_id) == first


def test_an_incomplete_regeneration_keeps_a_complete_saved_summary(summary_env, model, monkeypatch):
    """Analysis U1: a regeneration ending with failed parts does not replace a summary whose
    parts all completed; it is kept and returned."""
    first = service.summarize(summary_env.paper_id)

    def cut_off_method(system, prompt, on_retry=None, task="answer"):
        if "Section: Method." in prompt:
            raise llm.LLMError("cut off", reason="cut_off")
        return PromptReadingLLM()(system, prompt, on_retry)

    monkeypatch.setattr(llm, "generate", cut_off_method)
    kept = service.summarize(summary_env.paper_id, regenerate=True)
    assert kept == first
    assert service.saved_summary(summary_env.paper_id) == first


def test_retrying_a_failed_section_reruns_only_that_section(summary_env, model):
    summary = service.summarize(summary_env.paper_id)
    failed = dataclasses.replace(summary.sections[1], state="failed", text=None, reason="cut_off")
    sections = [summary.sections[0], failed, *summary.sections[2:]]
    resave(dataclasses.replace(summary, sections=sections))
    calls = len(model.calls)
    retried = service.summarize(summary_env.paper_id, retry_parts=["method"])
    new_calls = model.calls[calls:]
    assert len(new_calls) == 1 and "Section: Method." in new_calls[0][1]
    assert retried.sections[1].state == "verified"
    assert retried.tldr.text == summary.tldr.text
    assert retried.sections[0] == summary.sections[0] and retried.sections[2:] == summary.sections[2:]
    assert service.saved_summary(summary_env.paper_id) == retried


def test_retry_parts_needs_a_saved_summary_and_known_parts(summary_env, model):
    with pytest.raises(ValueError):
        service.summarize(summary_env.paper_id, retry_parts=["method"])
    service.summarize(summary_env.paper_id)
    with pytest.raises(ValueError):
        service.summarize(summary_env.paper_id, retry_parts=["conclusion"])


def test_summary_plan(summary_env, model):
    assert service.summary_plan(summary_env.paper_id) == {"max_requests": 6}
    assert service.summary_plan(summary_env.paper_id, retry_parts=["method"]) == {"max_requests": 1}
    assert service.summary_plan(summary_env.paper_id, retry_parts=["method", "data"]) == {"max_requests": 2}
    assert service.summary_plan(summary_env.paper_id, retry_parts=["method", "tldr"]) == {"max_requests": 2}
    assert service.summary_plan(summary_env.paper_id, retry_parts=["tldr"]) == {"max_requests": 1}


def test_summaries_survive_a_round_trip_through_the_cache(summary_env, model):
    summary = service.summarize(summary_env.paper_id)
    assert service.summary_from_dict(service.summary_to_dict(summary)) == summary
