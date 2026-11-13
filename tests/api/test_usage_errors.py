"""Usage, search and the error kinds of failed questions (contracts/web-api.md, spec FR-020–FR-026).

Nothing reaches the model or the provider: generate is scripted (or the real one over a fake
client), and the provider's key endpoint is stubbed or blocked by the autouse guard.
"""

from datetime import datetime, timezone

import pytest

import fake_llm as f
from paperpilot import llm
from paperpilot.errors import DailyLimitError, LLMError, RateLimitedError
from test_ask import HEADER, QUESTION, REPLY, ask_stream

REAL_GENERATE = llm.generate  # captured before fake_answers replaces it
UNTIL = datetime(2026, 10, 25, 13, 30, tzinfo=timezone.utc)
PROVIDER_TEXT = "upstream said: quota exhausted for key sk-or-v1-provider-detail"
USAGE_FIELDS = {"used", "limit", "remaining", "resets_at", "source"}


@pytest.fixture
def scripted(api_env):
    return api_env["llm"]


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def refreshes(monkeypatch):
    """Count provider refreshes; each reports the provider's figure 34 of 50."""
    calls = []

    def fake_refresh():
        calls.append(1)
        return llm.Usage(34, 50, 16, datetime(2026, 10, 26, tzinfo=timezone.utc), "provider")

    monkeypatch.setattr(llm, "refresh_usage", fake_refresh)
    return calls


# --- usage ---


def test_usage_reports_todays_requests(client, refreshes):
    body = client.get("/api/usage").json()
    assert body == {"used": 34, "limit": 50, "remaining": 16, "resets_at": "2026-10-26T00:00:00Z", "source": "provider"}


def test_usage_refreshes_from_the_provider_at_most_every_30_seconds(client, refreshes):
    clock = Clock()
    client.app.state.usage.clock = clock
    refreshes.clear()
    client.get("/api/usage")
    clock.now += 10
    client.get("/api/usage")
    assert len(refreshes) == 1
    clock.now += 21
    client.get("/api/usage")
    assert len(refreshes) == 2


def test_between_refreshes_the_local_count_is_reported(client, refreshes, monkeypatch):
    client.app.state.usage.clock = Clock()
    client.get("/api/usage")
    monkeypatch.setattr(llm, "usage", lambda: llm.Usage(35, 50, 15, datetime(2026, 10, 26, tzinfo=timezone.utc), "provider"))
    assert client.get("/api/usage").json()["used"] == 35


def test_usage_falls_back_to_the_local_count(client):
    """No stub: the guard makes the key endpoint fail, so the local count is used."""
    body = client.get("/api/usage").json()
    assert set(body) == USAGE_FIELDS
    assert (body["used"], body["limit"], body["source"]) == (0, 50, "local")


def test_an_answer_carries_the_usage_after_the_question(client_with_paper, scripted, refreshes):
    client_with_paper.app.state.usage.clock = Clock()
    refreshes.clear()
    scripted.add(REPLY)
    _, _, events = ask_stream(client_with_paper, {"question": QUESTION})
    assert events[-1][0] == "answer"
    assert events[-1][1]["usage"] == {"used": 34, "limit": 50, "remaining": 16,
                                      "resets_at": "2026-10-26T00:00:00Z", "source": "provider"}
    assert len(refreshes) == 1


# --- search (browse passages instead) ---


def test_search_returns_ranked_passages_without_the_model(client_with_paper, scripted):
    response = client_with_paper.post("/api/search", json={"query": "evaluation dataset", "k": 3}, headers=HEADER)
    assert response.status_code == 200
    results = response.json()["results"]
    assert [r["rank"] for r in results] == list(range(1, len(results) + 1)) and results
    assert set(results[0]) == {"rank", "score", "passage_id", "paper_id", "title", "section", "page", "text"}
    assert scripted.calls == []


@pytest.mark.parametrize(
    ("body", "status", "expected"),
    [
        ({"query": "   "}, 422, {"kind": "empty_question"}),
        ({"query": "x", "paper_ids": []}, 422, {"kind": "no_papers_selected"}),
        ({"query": "x", "paper_ids": ["000000000000"]}, 404, {"kind": "unknown_paper", "paper_id": "000000000000"}),
        ({"query": "x", "k": 0}, 422, {"kind": "invalid_request"}),
    ],
)
def test_search_refuses_bad_requests(client_with_paper, body, status, expected):
    response = client_with_paper.post("/api/search", json=body, headers=HEADER)
    assert (response.status_code, response.json()) == (status, expected)


# --- engine exceptions map to kinds (as the stream's error event) ---


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (LLMError(PROVIDER_TEXT, reason="busy"), {"kind": "model_busy", "attempts": llm.MAX_ATTEMPTS}),
        (LLMError(PROVIDER_TEXT, reason="timeout"), {"kind": "model_busy", "attempts": llm.MAX_ATTEMPTS}),
        (LLMError(PROVIDER_TEXT, reason="unreachable"), {"kind": "model_busy", "attempts": llm.MAX_ATTEMPTS}),
        *[(LLMError(PROVIDER_TEXT, reason=reason), {"kind": "model_unavailable", "reason": reason})
          for reason in ("not_listed", "unknown_model", "bad_key", "out_of_credits", "cut_off", "empty", "bad_request")],
        (DailyLimitError(50, 50, datetime(2026, 10, 26, tzinfo=timezone.utc)),
         {"kind": "daily_limit", "used": 50, "limit": 50, "resets_at": "2026-10-26T00:00:00Z"}),
        (RateLimitedError(UNTIL, daily=False), {"kind": "rate_limited", "until": "2026-10-25T13:30:00Z", "daily": False}),
        (RateLimitedError(UNTIL, daily=True), {"kind": "rate_limited", "until": "2026-10-25T13:30:00Z", "daily": True}),
    ],
    ids=lambda value: getattr(value, "reason", None) or (value.get("kind") if isinstance(value, dict) else None),
)
def test_each_engine_error_maps_to_its_kind(client_with_paper, scripted, error, expected):
    scripted.add(error)
    status, text, events = ask_stream(client_with_paper, {"question": QUESTION})
    assert status == 200
    assert events[-1] == ("error", expected)
    assert "quota exhausted" not in text and "Traceback" not in text and "sk-or-v1" not in text


def test_at_the_daily_limit_no_request_is_sent(client_with_paper, monkeypatch, refreshes):
    """The real generate over a fake client: the pre-check stops before any request."""
    monkeypatch.setenv("DAILY_REQUEST_LIMIT", "2")
    monkeypatch.setattr(llm, "refresh_usage", llm.usage)  # keep the local figure
    llm.count_request()
    llm.count_request()
    fake_client = f.FakeClient([f.ok(REPLY)])
    monkeypatch.setattr(llm, "_make_client", lambda settings: fake_client)
    monkeypatch.setattr(llm, "generate", REAL_GENERATE)
    _, _, events = ask_stream(client_with_paper, {"question": QUESTION})
    name, data = events[-1]
    assert (name, data["kind"], data["used"], data["limit"]) == ("error", "daily_limit", 2, 2)
    assert fake_client.calls == []


# --- nothing leaks ---


def test_no_response_leaks_the_key_a_traceback_or_provider_text(client_with_paper, scripted, api_env):
    key = api_env["api_key"]
    paper_id = client_with_paper.paper.paper_id
    scripted.add(LLMError(f"{PROVIDER_TEXT} {key}", reason="bad_key"))
    _, stream, _ = ask_stream(client_with_paper, {"question": QUESTION})
    bodies = [stream]
    for method, path, kwargs in [
        ("GET", "/api/status", {}),
        ("GET", "/api/usage", {}),
        ("GET", "/api/papers", {}),
        ("GET", "/api/jobs", {}),
        ("GET", "/api/passages/nope-1", {}),
        ("GET", "/api/papers/000000000000/pdf", {}),
        ("POST", "/api/search", {"json": {"query": "dataset"}, "headers": HEADER}),
        ("POST", "/api/search", {"json": {"query": ""}, "headers": HEADER}),
        ("POST", "/api/ask", {"json": {"question": ""}, "headers": HEADER}),
        ("POST", f"/api/papers/{paper_id}/reprocess", {}),
        ("DELETE", "/api/papers/000000000000", {"headers": HEADER}),
        ("GET", "/api/nothing-here", {}),
    ]:
        bodies.append(client_with_paper.request(method, path, **kwargs).text)
    for body in bodies:
        assert key not in body and "Traceback" not in body and "quota exhausted" not in body
