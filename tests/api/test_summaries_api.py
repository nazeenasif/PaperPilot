"""Summaries over HTTP (contracts/web-api.md Feature 4; spec US1, US2, US4). Scripted model only;
every write sends X-PaperPilot: 1."""

from collections.abc import Iterator

import pytest

from conftest import GuardedClient, wait_for_state
from paperpilot import llm, prompts
from test_ask import HEADER, parse_sse
from test_summarize import SENTINEL, PromptReadingLLM

FACETS = ["problem", "method", "data", "results", "limitations"]


@pytest.fixture
def summary_client(api_env, summary_paper, make_app, guarded, monkeypatch) -> Iterator[GuardedClient]:
    """A ready app over a library holding the summary paper, with a prompt-reading model."""
    from paperpilot.library import add_paper

    paper = add_paper(summary_paper)
    model = PromptReadingLLM()
    monkeypatch.setattr(llm, "generate", model)
    app, _ = make_app()
    with guarded(app) as client:
        wait_for_state(client, "ready")
        client.paper = paper  # type: ignore[attr-defined]
        client.model = model  # type: ignore[attr-defined]
        yield client


def summarize_stream(client, paper_id: str, body: dict | None = None) -> tuple[int, str, list]:
    with client.stream("POST", f"/api/summaries/{paper_id}", json=body or {}, headers=HEADER) as response:
        text = "".join(response.iter_text())
    return response.status_code, text, parse_sse(text) if response.status_code == 200 else []


# --- US1: list and stream ---


def test_the_summarize_tab_lists_papers_with_their_status(summary_client):
    body = summary_client.get("/api/summaries").json()
    assert body["plan"] == {"max_requests": 6}
    [paper] = body["papers"]
    assert paper["paper_id"] == summary_client.paper.paper_id and paper["title"] == summary_client.paper.title
    assert paper["summary"] == {"status": "none", "created_at": None, "model": None}


def test_a_summary_streams_plan_progress_parts_then_the_summary(summary_client):
    status, _, events = summarize_stream(summary_client, summary_client.paper.paper_id)
    assert status == 200
    names = [name for name, _ in events]
    assert names[0] == "plan" and names[-1] == "summary"
    assert events[0][1] == {"max_requests": 6, "parts": [*FACETS, "tldr"]}
    assert [d["part"] for n, d in events if n == "part"] == [*FACETS, "tldr"]
    summary = events[-1][1]
    assert {"paper_id", "title", "arxiv_id", "tldr", "sections", "passages", "plan", "requests", "model",
            "prompt_version", "created_at", "status", "stale_reason", "verified_parts"} <= set(summary)
    assert [s["part"] for s in summary["sections"]] == FACETS
    assert summary["verified_parts"] == 6 and summary["requests"] == {"planned": 6, "retries": 0}


def test_no_event_carries_a_parts_text_before_its_part_event(summary_client):
    _, _, events = summarize_stream(summary_client, summary_client.paper.paper_id)
    for name, data in events:
        if SENTINEL in repr(data):
            assert name in ("part", "summary"), name


def test_progress_names_the_part_and_step(summary_client):
    _, _, events = summarize_stream(summary_client, summary_client.paper.paper_id)
    steps = [(d["part"], d["step"]) for n, d in events if n == "progress" and d["part"] == "data"]
    assert steps == [("data", "searching"), ("data", "reading"), ("data", "generating"), ("data", "checking")]


def test_errors_before_the_stream_are_plain_json(summary_client):
    response = summary_client.post("/api/summaries/000000000000", json={}, headers=HEADER)
    assert (response.status_code, response.json()) == (404, {"kind": "unknown_paper", "paper_id": "000000000000"})
    response = summary_client.post(f"/api/summaries/{summary_client.paper.paper_id}",
                                   json={"retry_parts": ["conclusion"]}, headers=HEADER)
    assert (response.status_code, response.json()) == (422, {"kind": "invalid_request"})
    assert summary_client.model.calls == []


def test_summarizing_needs_the_write_header(summary_client):
    response = summary_client.post(f"/api/summaries/{summary_client.paper.paper_id}", json={})
    assert response.status_code == 403 and summary_client.model.calls == []


def test_no_response_leaks_the_key_or_a_traceback(summary_client, api_env):
    _, text, _ = summarize_stream(summary_client, summary_client.paper.paper_id)
    listing = summary_client.get("/api/summaries").text
    for body in (text, listing):
        assert api_env["api_key"] not in body and "Traceback" not in body


# --- US2: saved summaries over HTTP ---


def test_get_before_any_summary_is_not_saved_with_the_plan(summary_client):
    response = summary_client.get(f"/api/summaries/{summary_client.paper.paper_id}")
    assert (response.status_code, response.json()) == (404, {"kind": "not_saved", "plan": {"max_requests": 6}})


def test_get_after_a_summary_returns_it_current(summary_client):
    _, _, events = summarize_stream(summary_client, summary_client.paper.paper_id)
    response = summary_client.get(f"/api/summaries/{summary_client.paper.paper_id}")
    body = response.json()
    assert response.status_code == 200
    assert (body["status"], body["stale_reason"], body["model"]) == ("current", None, "test/model:free")
    assert body["created_at"] == events[-1][1]["created_at"]
    assert body["plan"] == {"max_requests": 6}
    listed = summary_client.get("/api/summaries").json()["papers"][0]["summary"]
    assert listed == {"status": "current", "created_at": body["created_at"], "model": "test/model:free"}


def test_a_second_post_reuses_the_saved_summary_with_zero_requests(summary_client):
    summarize_stream(summary_client, summary_client.paper.paper_id)
    calls = len(summary_client.model.calls)
    _, _, events = summarize_stream(summary_client, summary_client.paper.paper_id)
    assert [name for name, _ in events] == ["summary"]
    assert len(summary_client.model.calls) == calls


def test_a_model_change_makes_the_saved_summary_stale(summary_client, monkeypatch):
    summarize_stream(summary_client, summary_client.paper.paper_id)
    monkeypatch.setenv("LLM_MODEL", "other/model:free")
    body = summary_client.get(f"/api/summaries/{summary_client.paper.paper_id}").json()
    assert (body["status"], body["stale_reason"]) == ("stale", "model_changed")


def test_after_deleting_the_paper_its_summary_is_gone(summary_client):
    summarize_stream(summary_client, summary_client.paper.paper_id)
    summary_client.delete(f"/api/papers/{summary_client.paper.paper_id}", headers=HEADER)
    response = summary_client.get(f"/api/summaries/{summary_client.paper.paper_id}")
    assert (response.status_code, response.json()["kind"]) == (404, "unknown_paper")


def test_regenerate_through_the_stream(summary_client):
    summarize_stream(summary_client, summary_client.paper.paper_id)
    calls = len(summary_client.model.calls)
    _, _, events = summarize_stream(summary_client, summary_client.paper.paper_id, {"regenerate": True})
    assert events[0][0] == "plan" and events[-1][0] == "summary"
    assert len(summary_client.model.calls) == calls + 6


def test_retry_parts_through_the_stream(summary_client):
    summarize_stream(summary_client, summary_client.paper.paper_id)
    calls = len(summary_client.model.calls)
    _, _, events = summarize_stream(summary_client, summary_client.paper.paper_id, {"retry_parts": ["method"]})
    assert events[0] == ("plan", {"max_requests": 1, "parts": ["method"]})
    assert [d["part"] for n, d in events if n == "part"] == ["method"]
    assert len(summary_client.model.calls) == calls + 1
    assert events[-1][1]["tldr"]["built_without"] == ["method"]


def test_retry_parts_without_a_saved_summary_is_not_saved(summary_client):
    response = summary_client.post(f"/api/summaries/{summary_client.paper.paper_id}",
                                   json={"retry_parts": ["method"]}, headers=HEADER)
    assert (response.status_code, response.json()["kind"]) == (404, "not_saved")


# --- US4: part states over HTTP ---


def test_part_states_arrive_as_part_events_and_the_stream_still_ends_with_the_summary(summary_client, monkeypatch):
    from paperpilot.errors import LLMError

    model = PromptReadingLLM({"method": "No citation here.", "data": "Experiments use GLUE [99].",
                              "tldr": "Uncited summary sentence."})

    def generate(system, prompt, on_retry=None, task="answer"):
        if "Section: Results." in prompt:
            raise LLMError("cut off", reason="cut_off")
        return model(system, prompt, on_retry)

    monkeypatch.setattr(llm, "generate", generate)
    _, _, events = summarize_stream(summary_client, summary_client.paper.paper_id)
    parts = {d["part"]: d for n, d in events if n == "part"}
    assert (parts["method"]["state"], parts["method"]["reason"]) == ("not_reported", "no_citations")
    assert (parts["data"]["state"], parts["data"]["citations"]["invalid"]) == ("held_back", [99])
    assert parts["data"]["rejected_text"] == "Experiments use GLUE [99]."
    assert (parts["results"]["state"], parts["results"]["reason"]) == ("failed", "cut_off")
    assert (parts["tldr"]["state"], parts["tldr"]["warning"]) == ("held_back", "sentence 1 has no citation")
    for name, part in parts.items():
        assert (part["rejected_text"] is not None) == (part["state"] == "held_back"), name
        assert (part["text"] is not None) == (part["state"] == "verified"), name
    assert events[-1][0] == "summary" and events[-1][1]["verified_parts"] == 2
