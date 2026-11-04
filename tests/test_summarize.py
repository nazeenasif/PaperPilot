"""summarize(): query-focused sections, run-wide numbering, per-part validation and the TL;DR
(spec US1, FR-002–FR-005, FR-012; research R1–R3). Scripted model only; no network."""

import re
from datetime import datetime

import pytest

from paperpilot import library, llm, prompts, service
from paperpilot.errors import UnknownPaperError
from paperpilot.library import SearchResult
from paperpilot.llm import LLMReply

FACET_ORDER = ["problem", "method", "data", "results", "limitations"]
SENTINEL = "zebra-sentinel"  # appears only in model replies, to catch text leaking into early events


class PromptReadingLLM:
    """Stands in for llm.generate: cites the first passage of each section prompt, and writes
    a TL;DR that cites the first verified section's numbers. Records every prompt."""

    def __init__(self, overrides: dict[str, str] | None = None) -> None:
        self.overrides = overrides or {}
        self.calls: list[tuple[str, str]] = []

    def __call__(self, system: str, prompt: str, on_retry=None, task: str = "answer") -> LLMReply:
        self.calls.append((system, prompt))
        if system == prompts.TLDR_INSTRUCTION:
            numbers = re.findall(r"\[(\d+)", prompt)
            text = self.overrides.get("tldr", f"The paper studies efficient adaptation {SENTINEL} [{numbers[0]}].")
        else:
            facet = re.search(r"Section: (\w+)\.", prompt).group(1).lower()
            first = re.search(r'<passage id="(\d+)"', prompt).group(1)
            text = self.overrides.get(facet, f"The {facet} is described {SENTINEL} [{first}].")
        return LLMReply(text, 100, 40, 20, 1, 0.01)


@pytest.fixture
def model(summary_env, monkeypatch):
    fake = PromptReadingLLM()
    monkeypatch.setattr(llm, "generate", fake)
    return fake


@pytest.fixture
def searches(monkeypatch):
    """Record every library.search call made by summarize."""
    calls = []
    real = library.search

    def spy(query, k=None, paper_ids=None, sections=None):
        calls.append((query, k, paper_ids))
        return real(query, k=k, paper_ids=paper_ids, sections=sections)

    monkeypatch.setattr(library, "search", spy)
    return calls


def test_each_facet_retrieves_four_passages_from_the_paper(summary_env, model, searches):
    summary = service.summarize(summary_env.paper_id)
    assert [q for q, _, _ in searches] == [prompts.FACETS[f].query for f in FACET_ORDER]
    assert {(k, tuple(ids)) for _, k, ids in searches} == {(4, (summary_env.paper_id,))}
    assert {p.paper_id for p in summary.passages} == {summary_env.paper_id}


def test_the_summary_has_a_tldr_and_five_sections_in_order(summary_env, model):
    summary = service.summarize(summary_env.paper_id)
    assert [s.part for s in summary.sections] == FACET_ORDER
    assert summary.tldr.part == "tldr"
    assert all(s.state == "verified" for s in [*summary.sections, summary.tldr])
    assert summary.title == summary_env.title and summary.paper_id == summary_env.paper_id


def test_passages_are_numbered_once_per_summary(summary_env, model):
    summary = service.summarize(summary_env.paper_id)
    numbers = [p.number for p in summary.passages]
    ids = [p.passage_id for p in summary.passages]
    assert numbers == list(range(1, len(numbers) + 1)) and len(set(ids)) == len(ids)
    for section in summary.sections:
        assert set(section.passages) <= set(numbers) and len(section.passages) == 4
    # Six passages in the paper, five facets of four: passages are shared and keep one number.
    assert len(summary.passages) <= 6


def test_a_section_is_valid_only_against_its_own_passages(summary_env, monkeypatch):
    """Problem gets passages A, B (numbers 1, 2); Method gets C, D (3, 4). Method citing [1]
    is held back even though passage 1 exists in the summary."""
    ids = [r.passage_id for r in library.search("method", k=6, paper_ids=[summary_env.paper_id])]
    by_facet = {"problem": ids[:2], "method": ids[2:4], "data": ids[4:6], "results": ids[:2], "limitations": ids[2:4]}
    texts = {r.passage_id: r for r in library.search("method", k=6, paper_ids=[summary_env.paper_id])}

    def fake_search(query, k=None, paper_ids=None, sections=None):
        facet = next(f for f in FACET_ORDER if prompts.FACETS[f].query == query)
        return [SearchResult(i + 1, 0.9, pid, summary_env.paper_id, summary_env.title, texts[pid].section,
                             texts[pid].page, texts[pid].text) for i, pid in enumerate(by_facet[facet])]

    monkeypatch.setattr(library, "search", fake_search)
    fake = PromptReadingLLM({"method": "The method freezes the weights [1]."})
    monkeypatch.setattr(llm, "generate", fake)
    summary = service.summarize(summary_env.paper_id)
    method = summary.sections[1]
    assert method.passages == [3, 4]
    assert method.state == "held_back" and method.citations.invalid == [1]
    assert method.rejected_text == "The method freezes the weights [1]." and method.text is None
    assert summary.sections[0].state == "verified"


def test_the_tldr_is_built_from_verified_sections_only(summary_env, monkeypatch):
    fake = PromptReadingLLM({"data": "The data is unknown [99]."})
    monkeypatch.setattr(llm, "generate", fake)
    summary = service.summarize(summary_env.paper_id)
    tldr_prompt = fake.calls[-1][1]
    assert fake.calls[-1][0] == prompts.TLDR_INSTRUCTION
    assert '<section name="Data">' not in tldr_prompt and '<section name="Method">' in tldr_prompt
    assert summary.sections[2].state == "held_back"
    # The TL;DR cites Problem's first passage; other sections citing the same passage are sources too.
    assert summary.tldr.state == "verified" and "Problem" in summary.tldr.sources[0]
    assert "Data" not in summary.tldr.sources[0]


def test_the_result_records_requests_tokens_model_and_time(summary_env, model):
    summary = service.summarize(summary_env.paper_id)
    assert summary.requests == {"planned": 6, "retries": 0}
    assert summary.plan == {"max_requests": 6}
    assert all(p.requests == {"planned": 1, "retries": 0} for p in [*summary.sections, summary.tldr])
    assert summary.sections[0].tokens == {"input": 100, "output": 40, "reasoning": 20}
    assert summary.model == "test/model:free" and summary.prompt_version == prompts.SUMMARY_PROMPT_VERSION
    assert datetime.fromisoformat(summary.created_at).tzinfo is not None
    assert summary.verified_parts == 6


def test_events_stream_per_part_and_never_carry_unchecked_text(summary_env, model):
    events: list[tuple[str, dict]] = []
    service.summarize(summary_env.paper_id, on_event=lambda kind, detail: events.append((kind, detail)))
    assert events[0] == ("plan", {"max_requests": 6, "parts": [*FACET_ORDER, "tldr"]})
    method = [(k, d.get("step")) for k, d in events if d.get("part") == "method"]
    assert method == [("progress", "searching"), ("progress", "reading"), ("progress", "generating"),
                      ("progress", "checking"), ("part", None)]
    for i, (kind, detail) in enumerate(events):
        if SENTINEL in repr(detail):
            assert kind == "part" and detail["state"] == "verified", f"event {i} leaked text: {kind}"


def test_an_unknown_paper_sends_nothing(summary_env, model):
    with pytest.raises(UnknownPaperError):
        service.summarize("000000000000")
    assert model.calls == []
