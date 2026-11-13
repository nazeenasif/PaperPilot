"""compare(): one request per aspect, per-paper retrieval, per-cell validation, saving (spec US3,
FR-007-FR-010, FR-016-FR-020; research R4). Scripted model only; no network."""

import json
import re

import pytest

from paperpilot import library, llm, prompts, service, store
from paperpilot.errors import LLMError, UnknownPaperError
from paperpilot.llm import LLMReply

ASPECTS = ["method", "datasets", "results"]


def row_reply(**cells) -> str:
    return json.dumps({"cells": [{"paper": label, "text": text} for label, text in cells.items()]})


class RowLLM:
    """Stands in for llm.generate: each paper's cell cites that paper's first passage, unless
    `overrides` gives a reply for the row, by its label (a string, or an exception to raise)."""

    def __init__(self, overrides: dict | None = None) -> None:
        self.overrides = overrides or {}
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, system, prompt, on_retry=None, task="answer") -> LLMReply:
        self.calls.append((system, prompt, task))
        label = re.search(r"Row: (\w+)\.", prompt).group(1)
        override = self.overrides.get(label)
        if isinstance(override, Exception):
            raise override
        if override is not None:
            return LLMReply(override, 100, 40, 20, 1, 0.01)
        cells = {}
        for block in re.split(r"(?=Paper P\d:)", prompt):
            head = re.match(r"Paper (P\d):", block)
            first = re.search(r'<passage id="(\d+)"', block)
            if head:
                cells[head.group(1)] = f"{label} of this paper [{first.group(1)}]." if first else prompts.NOT_REPORTED
        return LLMReply(row_reply(**cells), 100, 40, 20, 1, 0.01)


@pytest.fixture
def papers(summary_env, second_paper):
    return [summary_env.paper_id, library.add_paper(second_paper).paper_id]


@pytest.fixture
def model(papers, monkeypatch):
    fake = RowLLM()
    monkeypatch.setattr(llm, "generate", fake)
    return fake


def use(monkeypatch, overrides):
    fake = RowLLM(overrides)
    monkeypatch.setattr(llm, "generate", fake)
    return fake


# --- input checks: 0 requests ---


@pytest.mark.parametrize(
    "shape",
    [
        lambda a, b: ([a], ASPECTS),
        lambda a, b: ([a, b, "c", "d", "e"], ASPECTS),
        lambda a, b: ([a, a], ASPECTS),
        lambda a, b: ([a, b], []),
        lambda a, b: ([a, b], ["poetry"]),
    ],
    ids=["one paper", "five papers", "duplicates", "no aspects", "unknown aspect"],
)
def test_bad_input_raises_with_no_request(papers, model, shape):
    with pytest.raises(ValueError):
        service.compare(*shape(*papers))
    assert model.calls == []


def test_an_unknown_paper_raises_with_no_request(papers, model):
    with pytest.raises(UnknownPaperError):
        service.compare([papers[0], "000000000000"], ASPECTS)
    assert model.calls == []


# --- retrieval and numbering ---


def test_one_request_per_aspect_with_the_comparison_limit(papers, model):
    comparison = service.compare(papers, ASPECTS)
    assert [row.aspect for row in comparison.rows] == ASPECTS
    assert len(model.calls) == 3 and {task for _, _, task in model.calls} == {"comparison"}
    assert {system for system, _, _ in model.calls} == {prompts.ROW_INSTRUCTION}
    assert comparison.requests == {"planned": 3, "retries": 0}


def test_every_paper_gets_the_same_number_of_passages(papers, model):
    comparison = service.compare(papers, ["results"])
    assert [len(cell.passages) for cell in comparison.rows[0].cells] == [3, 3]


def test_retrieval_uses_the_shared_facet_query_for_each_paper_alone(papers, model, monkeypatch):
    calls = []
    real = library.search

    def spy(query, k=None, paper_ids=None, sections=None):
        calls.append((query, k, paper_ids))
        return real(query, k=k, paper_ids=paper_ids, sections=sections)

    monkeypatch.setattr(library, "search", spy)
    service.compare(papers, ["datasets"])
    assert calls == [(prompts.FACETS["data"].query, 3, [papers[0]]), (prompts.FACETS["data"].query, 3, [papers[1]])]


def test_comparisons_exclude_related_work(tmp_path, make_pdf, summary_env, model_for_related):
    body = "We train a small network on a private collection of scanned documents and measure the layout it recovers. " * 3
    related = "Earlier systems proposed the method and model architecture in other ways, and report results. " * 4
    path = make_pdf(tmp_path / "related.pdf", references=False, title="A Study of Layout Recovery Methods",
                    sections=[("Abstract", body), ("2 Related Work", related), ("3 Method", body + " Method.")])
    comparison = service.compare([summary_env.paper_id, library.add_paper(path).paper_id], ["method"])
    assert "Related Work" not in {p.section for p in comparison.passages}


@pytest.fixture
def model_for_related(monkeypatch):
    monkeypatch.setattr(llm, "generate", RowLLM())


def test_a_limitations_row_prefers_its_sections_within_three_passages(papers, model):
    comparison = service.compare(papers, ["limitations"])
    numbered = {p.number: p for p in comparison.passages}
    first = comparison.rows[0].cells[0]
    assert len(first.passages) == 3 and "Limitations" in {numbered[n].section for n in first.passages}


def test_a_passage_keeps_one_number_across_rows(papers, model):
    comparison = service.compare(papers, ASPECTS)
    numbers = [p.number for p in comparison.passages]
    ids = [p.passage_id for p in comparison.passages]
    assert numbers == list(range(1, len(numbers) + 1)) and len(set(ids)) == len(ids)


def test_papers_are_labelled_in_the_researchers_order(papers, model):
    comparison = service.compare(list(reversed(papers)), ["method"])
    assert [p["label"] for p in comparison.papers] == ["P1", "P2"]
    assert [p["paper_id"] for p in comparison.papers] == list(reversed(papers))
    assert comparison.paper_ids == list(reversed(papers))


# --- each cell on its own ---


def test_cells_are_verified_and_cite_their_own_paper(papers, model):
    comparison = service.compare(papers, ["method"])
    by_number = {p.number: p for p in comparison.passages}
    for cell, paper_id in zip(comparison.rows[0].cells, papers):
        assert cell.part == f"method:{paper_id}" and cell.state == "verified"
        assert {by_number[n].paper_id for n in cell.citations.valid} == {paper_id}
    assert (comparison.verified_cells, comparison.total_cells) == (2, 2)


def test_citing_the_other_papers_passage_holds_back_only_that_cell(papers, monkeypatch):
    # Passages 1-3 belong to P1, so P2 citing [1] is invalid for P2's cell.
    use(monkeypatch, {"Method": row_reply(P1="A [1].", P2="B [1].")})
    [first, second] = service.compare(papers, ["method"]).rows[0].cells
    assert first.state == "verified"
    assert second.state == "held_back" and second.citations.invalid == [1] and second.text is None


def test_a_missing_cell_is_not_reported(papers, monkeypatch):
    use(monkeypatch, {"Method": row_reply(P1="A [1].")})
    second = service.compare(papers, ["method"]).rows[0].cells[1]
    assert (second.state, second.reason) == ("not_reported", "missing_cell")


def test_the_not_reported_sentence_is_not_reported(papers, monkeypatch):
    use(monkeypatch, {"Method": row_reply(P1="A [1].", P2=prompts.NOT_REPORTED)})
    second = service.compare(papers, ["method"]).rows[0].cells[1]
    assert second.state == "not_reported" and second.text is None


def test_a_cell_without_citations_is_not_reported(papers, monkeypatch):
    use(monkeypatch, {"Method": row_reply(P1="A [1].", P2="B without a citation.")})
    assert service.compare(papers, ["method"]).rows[0].cells[1].state == "not_reported"


# --- rows that fail ---


def test_a_malformed_reply_fails_its_row_and_the_next_still_runs(papers, monkeypatch):
    fake = use(monkeypatch, {"Method": "not json"})
    comparison = service.compare(papers, ["method", "results"])
    [method, results] = comparison.rows
    assert (method.state, method.reason, method.cells) == ("failed", "malformed", [])
    assert results.state == "ok" and all(c.state == "verified" for c in results.cells)
    assert len(fake.calls) == 2


@pytest.mark.parametrize("reason", ["cut_off", "empty"])
def test_a_cut_off_row_fails_alone(papers, monkeypatch, reason):
    use(monkeypatch, {"Method": LLMError("no", reason=reason, tokens={"output": 8192, "reasoning": 8000})})
    comparison = service.compare(papers, ["method", "results"])
    assert (comparison.rows[0].state, comparison.rows[0].reason) == ("failed", reason)
    assert comparison.rows[1].state == "ok"


def test_a_cut_off_row_keeps_its_token_counts(papers, monkeypatch):
    use(monkeypatch, {"Method": LLMError("no", reason="cut_off", tokens={"output": 8192, "reasoning": 8000})})
    assert service.compare(papers, ["method"]).rows[0].tokens == {"output": 8192, "reasoning": 8000}


def test_every_paper_below_the_threshold_is_not_reported_with_no_request(papers, model, monkeypatch):
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "0.999")
    row = service.compare(papers, ["method"]).rows[0]
    assert model.calls == []
    assert row.state == "ok" and {(c.state, c.reason) for c in row.cells} == {("not_reported", "below_threshold")}


def test_a_paper_below_the_threshold_is_sent_with_no_passages(papers, monkeypatch):
    fake = use(monkeypatch, {})
    real = service.facet_retrieval

    def gated(facet, paper_id, k=service.SUMMARY_PASSAGES):
        found = real(facet, paper_id, k)
        return service.FacetRetrieval(found.passages, -1.0 if paper_id == papers[1] else found.gate_score)

    monkeypatch.setattr(service, "facet_retrieval", gated)
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "0.0")
    [first, second] = service.compare(papers, ["method"]).rows[0].cells
    assert first.state == "verified"
    assert (second.state, second.reason, second.passages) == ("not_reported", "below_threshold", [])
    assert prompts.NOT_REPORTED in fake.calls[0][1]


def test_a_model_reply_for_a_paper_below_the_threshold_is_ignored(papers, monkeypatch):
    use(monkeypatch, {"Method": row_reply(P1="A [1].", P2="Invented [1].")})
    real = service.facet_retrieval

    def gated(facet, paper_id, k=service.SUMMARY_PASSAGES):
        found = real(facet, paper_id, k)
        return service.FacetRetrieval(found.passages, -1.0 if paper_id == papers[1] else found.gate_score)

    monkeypatch.setattr(service, "facet_retrieval", gated)
    second = service.compare(papers, ["method"]).rows[0].cells[1]
    assert (second.state, second.reason) == ("not_reported", "below_threshold")


# --- saving and reuse ---


def test_the_same_papers_and_aspects_in_any_order_reopen_with_no_request(papers, model):
    first = service.compare(papers, ["method", "results"])
    calls = len(model.calls)
    again = service.compare(list(reversed(papers)), ["results", "method"])
    assert len(model.calls) == calls and again.rows == first.rows and again.status == "current"


def test_saved_comparison_never_generates(papers, model):
    assert service.saved_comparison(papers, ASPECTS) is None
    first = service.compare(papers, ASPECTS)
    calls = len(model.calls)
    assert service.saved_comparison(list(reversed(papers)), ASPECTS).rows == first.rows
    assert len(model.calls) == calls


def test_regenerate_runs_again(papers, model):
    service.compare(papers, ["method"])
    calls = len(model.calls)
    service.compare(papers, ["method"], regenerate=True)
    assert len(model.calls) == calls + 1


def test_retrying_an_aspect_reruns_only_that_row(papers, monkeypatch):
    fake = use(monkeypatch, {"Results": "not json"})
    failed = service.compare(papers, ["method", "results"])
    assert failed.rows[1].state == "failed"
    fake.overrides = {}
    calls = len(fake.calls)
    done = service.compare(papers, ["method", "results"], retry_aspects=["results"])
    assert len(fake.calls) == calls + 1 and "Row: Results." in fake.calls[-1][1]
    assert done.rows[0] == failed.rows[0] and done.rows[1].state == "ok"
    assert done.requests == {"planned": 1, "retries": 0}


def test_retrying_an_aspect_that_is_not_in_the_comparison_raises(papers, model):
    service.compare(papers, ["method"])
    with pytest.raises(ValueError):
        service.compare(papers, ["method"], retry_aspects=["results"])


def test_retrying_with_nothing_saved_raises(papers, model):
    with pytest.raises(ValueError):
        service.compare(papers, ["method"], retry_aspects=["method"])
    assert model.calls == []


def test_the_plan_is_the_number_of_aspects_or_rows_retried(papers):
    assert service.comparison_plan(papers, ASPECTS) == {"max_requests": 3, "parts": ASPECTS}
    assert service.comparison_plan(papers, ASPECTS, retry_aspects=["results"]) == {"max_requests": 1, "parts": ["results"]}


# --- a failed run never replaces the last complete comparison (FR-019, FR-020) ---


def test_a_failed_regeneration_keeps_the_complete_comparison_and_can_be_finished(papers, model, monkeypatch):
    first = service.compare(papers, ["method", "results"])
    fake = use(monkeypatch, {"Results": "not json"})
    kept = service.compare(papers, ["method", "results"], regenerate=True)
    assert kept.rows == first.rows and kept.pending["retry_aspects"] == ["results"]
    assert kept.pending["failed_aspects"] == ["results"]
    fake.overrides = {}
    done = service.compare(papers, ["method", "results"], retry_aspects=["results"])
    assert done.pending is None and all(r.state == "ok" for r in done.rows)
    assert service.saved_comparison(papers, ["method", "results"]).pending is None


def test_re_processing_marks_a_comparison_earlier_and_blocks_retries(papers, model):
    service.compare(papers, ["method"])
    library.reprocess_paper(papers[0])
    saved = service.saved_comparison(papers, ["method"])
    assert (saved.status, saved.stale_reason) == ("stale", "passages_changed")
    with pytest.raises(ValueError, match="earlier"):
        service.compare(papers, ["method"], retry_aspects=["method"])


def test_a_changed_passage_is_marked_on_an_earlier_comparison(papers, model, monkeypatch):
    service.compare(papers, ["method"])
    library.reprocess_paper(papers[0])
    monkeypatch.setattr(store, "get_passage", lambda passage_id: None)
    assert all(p.moved for p in service.saved_comparison(papers, ["method"]).passages)


# --- events ---


def test_events_arrive_in_order_and_carry_no_text_before_the_check(papers, monkeypatch):
    use(monkeypatch, {"Results": "not json"})
    events = []
    service.compare(papers, ["method", "results"], on_event=lambda kind, detail: events.append((kind, detail)))
    assert events[0] == ("plan", {"max_requests": 2, "parts": ["method", "results"]})
    kinds = [kind for kind, _ in events]
    assert kinds.count("part") == 2 and kinds.count("row_failed") == 1
    assert ("row_failed", {"aspect": "results", "reason": "malformed"}) in events
    assert {d["step"] for k, d in events if k == "progress"} >= {"searching", "reading", "generating", "checking"}
    assert all(d["part"] in ("method", "results") for k, d in events if k == "progress")
    assert all(d["part"].startswith("method:") for k, d in events if k == "part")
    for kind, detail in events:
        if kind == "progress":
            assert "text" not in detail
