"""One model task at a time, and limits before and during a run, over HTTP (spec US5, FR-023-FR-025;
research R8). Scripted model only."""

import threading
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest

from conftest import GuardedClient, wait_for_state
from paperpilot import library, llm
from paperpilot.errors import DailyLimitError
from test_ask import HEADER, parse_sse
from test_compare import RowLLM
from test_summarize import PromptReadingLLM

RESETS = datetime(2026, 11, 9, tzinfo=timezone.utc)


class Held(PromptReadingLLM):
    """Waits at the first request until released, so a run can be held mid-way."""

    def __init__(self):
        super().__init__()
        self.started, self.release = threading.Event(), threading.Event()

    def __call__(self, system, prompt, on_retry=None, task="answer"):
        self.started.set()
        assert self.release.wait(30)
        return super().__call__(system, prompt, on_retry, task)


@pytest.fixture
def run_client(api_env, summary_paper, second_paper, make_app, guarded, monkeypatch) -> Iterator[GuardedClient]:
    first = library.add_paper(summary_paper)
    second = library.add_paper(second_paper)
    monkeypatch.setattr(llm, "generate", PromptReadingLLM())
    app, _ = make_app()
    with guarded(app) as client:
        wait_for_state(client, "ready")
        client.ids = [first.paper_id, second.paper_id]  # type: ignore[attr-defined]
        yield client


def stream_events(client, path: str, body: dict) -> list:
    with client.stream("POST", path, json=body, headers=HEADER) as response:
        assert response.status_code == 200
        return parse_sse("".join(response.iter_text()))


# --- one model task at a time ---


def test_while_a_summary_runs_other_tasks_are_busy(run_client, monkeypatch):
    held = Held()
    monkeypatch.setattr(llm, "generate", held)
    a, b = run_client.ids
    thread = threading.Thread(target=stream_events, args=(run_client, f"/api/summaries/{a}", {}))
    thread.start()
    try:
        assert held.started.wait(30)
        for path, body in [("/api/ask", {"question": "What is it?"}),
                           ("/api/comparisons", {"paper_ids": [a, b], "aspects": ["method"]}),
                           (f"/api/summaries/{b}", {})]:
            refused = run_client.post(path, json=body, headers=HEADER)
            assert (refused.status_code, refused.json()) == (409, {"kind": "busy_task"}), path
    finally:
        held.release.set()
        thread.join(60)


def test_while_a_comparison_runs_a_summary_is_busy(run_client, monkeypatch):
    held = threading.Event()
    release = threading.Event()
    rows = RowLLM()

    def waits(system, prompt, on_retry=None, task="answer"):
        held.set()
        assert release.wait(30)
        return rows(system, prompt, on_retry, task)

    monkeypatch.setattr(llm, "generate", waits)
    a, b = run_client.ids
    thread = threading.Thread(target=stream_events, args=(run_client, "/api/comparisons", {"paper_ids": [a, b], "aspects": ["method"]}))
    thread.start()
    try:
        assert held.wait(30)
        refused = run_client.post(f"/api/summaries/{a}", json={}, headers=HEADER)
        assert (refused.status_code, refused.json()) == (409, {"kind": "busy_task"})
    finally:
        release.set()
        thread.join(60)


def test_while_a_question_runs_a_summary_is_busy(run_client):
    lock = run_client.app.state.paperpilot.model_lock
    assert lock.acquire(blocking=False)
    try:
        refused = run_client.post(f"/api/summaries/{run_client.ids[0]}", json={}, headers=HEADER)
        assert (refused.status_code, refused.json()) == (409, {"kind": "busy_task"})
    finally:
        lock.release()


def test_a_refused_start_does_not_release_the_running_tasks_lock(run_client):
    lock = run_client.app.state.paperpilot.model_lock
    assert lock.acquire(blocking=False)
    try:
        run_client.post(f"/api/summaries/{run_client.ids[0]}", json={}, headers=HEADER)
        assert lock.locked()
    finally:
        lock.release()


def test_the_lock_is_free_after_a_run(run_client):
    stream_events(run_client, f"/api/summaries/{run_client.ids[0]}", {})
    assert not run_client.app.state.paperpilot.model_lock.locked()


# --- too few requests left, before the stream ---


def use_up(left: int, limit: int, monkeypatch) -> None:
    monkeypatch.setenv("DAILY_REQUEST_LIMIT", str(limit))
    for _ in range(limit - left):
        llm.count_request()


def test_a_summary_with_too_few_requests_left_is_refused_before_the_stream(run_client, monkeypatch):
    model = PromptReadingLLM()
    monkeypatch.setattr(llm, "generate", model)
    use_up(5, 10, monkeypatch)
    refused = run_client.post(f"/api/summaries/{run_client.ids[0]}", json={}, headers=HEADER)
    body = refused.json()
    assert refused.status_code == 429 and body["kind"] == "daily_limit"
    assert (body["needed"], body["used"], body["limit"]) == (6, 5, 10) and body["resets_at"]
    assert model.calls == []
    assert not run_client.app.state.paperpilot.model_lock.locked()


def test_a_comparison_with_too_few_requests_left_is_refused_before_the_stream(run_client, monkeypatch):
    rows = RowLLM()
    monkeypatch.setattr(llm, "generate", rows)
    use_up(2, 10, monkeypatch)
    body = {"paper_ids": run_client.ids, "aspects": ["problem", "method", "results"]}
    refused = run_client.post("/api/comparisons", json=body, headers=HEADER)
    assert refused.status_code == 429 and refused.json()["needed"] == 3 and rows.calls == []


def test_a_retry_is_checked_against_its_own_plan(run_client, monkeypatch):
    paper = run_client.ids[0]
    stream_events(run_client, f"/api/summaries/{paper}", {})
    use_up(1, 10, monkeypatch)
    assert run_client.post(f"/api/summaries/{paper}", json={"retry_parts": ["results", "tldr"]}, headers=HEADER).status_code == 429
    events = stream_events(run_client, f"/api/summaries/{paper}", {"retry_parts": ["results"]})
    assert events[-1][0] == "summary"


def test_a_saved_result_still_opens_with_no_requests_left(run_client, monkeypatch):
    paper = run_client.ids[0]
    stream_events(run_client, f"/api/summaries/{paper}", {})
    use_up(0, 10, monkeypatch)
    assert run_client.get(f"/api/summaries/{paper}").status_code == 200
    events = stream_events(run_client, f"/api/summaries/{paper}", {})  # not regenerating: no request
    assert events[-1][0] == "summary"


def test_regenerating_with_too_few_requests_left_is_refused(run_client, monkeypatch):
    paper = run_client.ids[0]
    stream_events(run_client, f"/api/summaries/{paper}", {})
    use_up(0, 10, monkeypatch)
    assert run_client.post(f"/api/summaries/{paper}", json={"regenerate": True}, headers=HEADER).status_code == 429


# --- stopped during a run ---


def test_a_summary_stopped_mid_way_ends_with_its_remaining_parts_not_started(run_client, monkeypatch):
    calls = []

    class Stops(PromptReadingLLM):
        def __call__(self, system, prompt, on_retry=None, task="answer"):
            calls.append(prompt)
            if len(calls) == 3:
                raise DailyLimitError(50, 50, RESETS)
            return super().__call__(system, prompt, on_retry, task)

    monkeypatch.setattr(llm, "generate", Stops())
    events = stream_events(run_client, f"/api/summaries/{run_client.ids[0]}", {})
    name, summary = events[-1]
    assert name == "summary" and len(calls) == 3
    assert [s["state"] for s in summary["sections"]] == ["verified", "verified", "not_started", "not_started", "not_started"]
    assert summary["tldr"]["state"] == "not_started" and summary["tldr"]["reason"] == "daily_limit"
    assert summary["sections"][2]["until"] == RESETS.isoformat()


def test_a_run_stopped_before_anything_finished_ends_with_an_error(run_client, monkeypatch):
    def stops(system, prompt, on_retry=None, task="answer"):
        raise DailyLimitError(50, 50, RESETS)

    monkeypatch.setattr(llm, "generate", stops)
    events = stream_events(run_client, f"/api/summaries/{run_client.ids[0]}", {})
    assert events[-1][0] == "error" and events[-1][1]["kind"] == "daily_limit"
