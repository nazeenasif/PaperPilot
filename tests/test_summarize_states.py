""""Not reported", held-back and failed parts; the rest of the summary stays visible
(spec US4, FR-011, FR-014; research R3, R5). Scripted replies per facet; no network."""

import pytest

from paperpilot import llm, prompts, service
from paperpilot.errors import LLMError
from test_summarize import PromptReadingLLM


def run(monkeypatch, paper_id, overrides=None, fail=None):
    """Summarize with scripted replies; `fail` maps a facet (or "tldr") to an LLMError reason."""
    fake = PromptReadingLLM(overrides)

    def generate(system, prompt, on_retry=None):
        part = "tldr" if system == prompts.TLDR_INSTRUCTION else prompt.split("Section: ")[1].split(".")[0].lower()
        if fail and part in fail:
            fake.calls.append((system, prompt))
            raise LLMError("scripted failure", reason=fail[part])
        return fake(system, prompt, on_retry)

    monkeypatch.setattr(llm, "generate", generate)
    return service.summarize(paper_id, regenerate=True), fake


def states(summary):
    return {p.part: p.state for p in [*summary.sections, summary.tldr]}


@pytest.mark.parametrize(
    ("reply", "reason"),
    [("The method freezes weights.", "no_citations"),
     (prompts.NOT_REPORTED, "model_not_found"),
     (prompts.NOT_FOUND, "model_not_found")],
)
def test_a_section_without_support_is_not_reported(summary_env, monkeypatch, reply, reason):
    summary, _ = run(monkeypatch, summary_env.paper_id, {"method": reply})
    method = summary.sections[1]
    assert (method.state, method.reason, method.text, method.rejected_text) == ("not_reported", reason, None, None)
    assert states(summary) == {"problem": "verified", "method": "not_reported", "data": "verified",
                               "results": "verified", "limitations": "verified", "tldr": "verified"}


def test_a_facet_below_the_relevance_gate_makes_no_request(summary_env, monkeypatch):
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "0.99")
    summary, fake = run(monkeypatch, summary_env.paper_id)
    assert all(s.reason == "below_threshold" and s.state == "not_reported" for s in summary.sections)
    assert summary.tldr.reason == "no_verified_sections"
    assert fake.calls == [] and summary.requests == {"planned": 0, "retries": 0}
    assert summary.plan == {"max_requests": 6}


def test_a_section_citing_outside_its_passages_is_held_back(summary_env, monkeypatch):
    summary, _ = run(monkeypatch, summary_env.paper_id, {"data": "Experiments use GLUE [99]."})
    data = summary.sections[2]
    assert data.state == "held_back" and data.text is None
    assert data.rejected_text == "Experiments use GLUE [99]." and data.citations.invalid == [99]
    assert "[99]" in data.warning
    assert [s.state for s in summary.sections].count("verified") == 4


@pytest.mark.parametrize("reason", ["cut_off", "empty"])
def test_a_cut_off_or_empty_section_fails_alone_and_the_run_continues(summary_env, monkeypatch, reason):
    summary, fake = run(monkeypatch, summary_env.paper_id, fail={"results": reason})
    results = summary.sections[3]
    assert (results.state, results.reason, results.text) == ("failed", reason, None)
    assert results.requests["planned"] == 1
    assert states(summary)["limitations"] == "verified" and summary.tldr.state == "verified"
    assert len(fake.calls) == 6


def test_a_tldr_failing_its_check_is_held_back_while_the_sections_stay(summary_env, monkeypatch):
    summary, _ = run(monkeypatch, summary_env.paper_id, {"tldr": "It is the best method ever written."})
    tldr = summary.tldr
    assert tldr.state == "held_back" and tldr.text is None
    assert tldr.rejected_text == "It is the best method ever written."
    assert tldr.warning == "sentence 1 has no citation"
    assert all(s.state == "verified" for s in summary.sections)


def test_a_tldr_with_a_number_its_sources_lack_is_held_back(summary_env, monkeypatch):
    summary, _ = run(monkeypatch, summary_env.paper_id, {"tldr": "It is 500 times smaller [1]."})
    assert summary.tldr.state == "held_back" and "500" in summary.tldr.warning


def test_no_verified_section_means_no_tldr_request(summary_env, monkeypatch):
    overrides = {f: "No citation here." for f in prompts.FACETS}
    summary, fake = run(monkeypatch, summary_env.paper_id, overrides)
    assert (summary.tldr.state, summary.tldr.reason) == ("not_reported", "no_verified_sections")
    assert len(fake.calls) == 5 and all(c[0] == prompts.SECTION_INSTRUCTION for c in fake.calls)


def test_text_is_only_on_verified_parts_and_rejected_text_only_on_held_back(summary_env, monkeypatch):
    summary, _ = run(monkeypatch, summary_env.paper_id,
                     {"method": "No citation.", "data": "GLUE [99].", "tldr": "Uncited."}, fail={"results": "cut_off"})
    for part in [*summary.sections, summary.tldr]:
        assert (part.text is not None) == (part.state == "verified"), part.part
        assert (part.rejected_text is not None) == (part.state == "held_back"), part.part
