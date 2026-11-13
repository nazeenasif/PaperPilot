"""POST /api/ask: progress events, then the checked answer (contracts/web-api.md, spec FR-004–FR-011)."""

import json
from datetime import datetime, timezone

import pytest

from paperpilot import prompts
from paperpilot.errors import DailyLimitError, LLMError, RateLimitedError

HEADER = {"X-PaperPilot": "1"}
QUESTION = "Which evaluation dataset was used?"
REPLY = "Evaluated on a benchmark dataset of questions [1]."
ANSWER_FIELDS = {
    "question", "standalone_question", "rewrite_applied", "rewrite_fallback_reason", "text", "not_found",
    "fallback_reason", "warning", "rejected_answer", "citations", "verified", "passages", "papers_read",
    "word_count", "llm_calls", "requests", "timings", "tokens", "usage",
}


def parse_sse(text: str) -> list[tuple[str, object]]:
    """(event, data) pairs from an event-stream body; comments (pings) are skipped."""
    events = []
    for chunk in text.replace("\r\n", "\n").split("\n\n"):
        name, data = "message", []
        for line in chunk.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
        if data:
            events.append((name, json.loads("\n".join(data))))
    return events


def ask_stream(client, body: dict) -> tuple[int, str, list]:
    with client.stream("POST", "/api/ask", json=body, headers=HEADER) as response:
        text = "".join(response.iter_text())
    return response.status_code, text, parse_sse(text) if response.status_code == 200 else []


@pytest.fixture
def scripted(api_env):
    return api_env["llm"]


# --- the stream ---


def test_answered_question_streams_progress_then_the_answer(client_with_paper, scripted, api_env):
    scripted.add(REPLY)
    status, text, events = ask_stream(client_with_paper, {"question": QUESTION})
    assert status == 200
    assert api_env["api_key"] not in text
    names = [name for name, _ in events]
    assert names[-1] == "answer"
    assert [data["step"] for name, data in events if name == "progress"] == ["searching", "reading", "generating", "checking"]
    answer = events[-1][1]
    assert set(answer) == ANSWER_FIELDS
    assert answer["text"] == REPLY and answer["verified"] is True and answer["not_found"] is False
    assert answer["citations"] == {"valid": [1], "invalid": [], "uncited_sentences": []}
    assert answer["papers_read"] == 1
    assert [p["number"] for p in answer["passages"]] == list(range(1, len(answer["passages"]) + 1))
    first = answer["passages"][0]
    assert set(first) == {"number", "passage_id", "paper_id", "title", "section", "page", "score", "text"}
    assert set(answer["requests"]) == {"planned", "retries"}
    assert set(answer["timings"]) == {"rewrite", "retrieve", "generate"}
    reading = next(data for name, data in events if name == "progress" and data["step"] == "reading")
    assert reading == {"step": "reading", "passages": len(answer["passages"]), "papers": 1}


def test_no_answer_text_is_sent_before_the_answer_event(client_with_paper, scripted):
    scripted.add(REPLY)
    _, _, events = ask_stream(client_with_paper, {"question": QUESTION})
    before = json.dumps([data for name, data in events if name != "answer"])
    assert REPLY not in before and "benchmark dataset of questions" not in before


def test_not_found_is_an_answer_event_and_not_verified(client_with_paper, scripted):
    scripted.add(prompts.NOT_FOUND)
    _, _, events = ask_stream(client_with_paper, {"question": QUESTION})
    name, answer = events[-1]
    assert name == "answer"
    assert answer["text"] == prompts.NOT_FOUND and answer["not_found"] is True
    assert answer["fallback_reason"] == "model_not_found" and answer["verified"] is False


def test_a_held_back_answer_carries_the_unverified_text(client_with_paper, scripted):
    held = "Evaluated on a benchmark [99]."
    scripted.add(held)
    _, _, events = ask_stream(client_with_paper, {"question": QUESTION})
    answer = events[-1][1]
    assert answer["text"] == prompts.NOT_FOUND and answer["verified"] is False
    assert answer["rejected_answer"] == held
    assert answer["fallback_reason"] == "invalid_citations"
    assert answer["citations"]["invalid"] == [99]
    assert answer["warning"]


def test_retry_waits_are_streamed(client_with_paper, scripted):
    from paperpilot.llm import RetryNotice

    scripted.add(RetryNotice(attempt=1, max_attempts=4, wait_seconds=8.0, reason="rate_limited"), REPLY)
    _, _, events = ask_stream(client_with_paper, {"question": QUESTION})
    waits = [data for name, data in events if name == "retry_wait"]
    assert waits == [{"attempt": 1, "max_attempts": 4, "wait_seconds": 8.0, "reason": "rate_limited"}]
    assert events[-1][0] == "answer"


def test_a_follow_up_reports_rewriting_and_its_standalone_question(client_with_paper, scripted):
    scripted.add("Which evaluation dataset does the benchmark use?", REPLY)
    _, _, events = ask_stream(client_with_paper, {
        "question": "Which dataset does it use?",
        "history": [{"role": "user", "text": QUESTION}, {"role": "assistant", "text": REPLY}],
    })
    assert [d["step"] for n, d in events if n == "progress"][0] == "rewriting"
    answer = events[-1][1]
    assert answer["rewrite_applied"] is True
    assert answer["standalone_question"] == "Which evaluation dataset does the benchmark use?"


# --- errors during the stream end with an error event ---

RESET = datetime(2026, 10, 26, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "error, expected",
    [
        (LLMError("still limited", reason="busy"), {"kind": "model_busy", "attempts": 4}),
        (LLMError("timed out", reason="timeout"), {"kind": "model_busy", "attempts": 4}),
        (LLMError("no such model", reason="unknown_model"), {"kind": "model_unavailable", "reason": "unknown_model"}),
        (LLMError("cut off", reason="cut_off"), {"kind": "model_unavailable", "reason": "cut_off"}),
        (DailyLimitError(used=50, limit=50, resets_at=RESET),
         {"kind": "daily_limit", "used": 50, "limit": 50, "resets_at": "2026-10-26T00:00:00Z"}),
        (RateLimitedError(until=RESET, daily=False), {"kind": "rate_limited", "until": "2026-10-26T00:00:00Z", "daily": False}),
        (RuntimeError("database exploded"), {"kind": "internal"}),
    ],
)
def test_a_failure_ends_the_stream_with_an_error_event(client_with_paper, scripted, error, expected):
    scripted.add(error)
    _, text, events = ask_stream(client_with_paper, {"question": QUESTION})
    assert events[-1] == ("error", expected)
    assert "exploded" not in text and "Traceback" not in text


# --- validation happens before the stream (plain JSON errors) ---


def test_an_empty_question_is_refused(client_with_paper, scripted):
    response = client_with_paper.post("/api/ask", json={"question": "   "}, headers=HEADER)
    assert response.status_code == 422
    assert response.json() == {"kind": "empty_question"}
    assert scripted.calls == []


def test_an_empty_paper_selection_is_refused(client_with_paper):
    response = client_with_paper.post("/api/ask", json={"question": QUESTION, "paper_ids": []}, headers=HEADER)
    assert response.status_code == 422
    assert response.json() == {"kind": "no_papers_selected"}


def test_an_unknown_paper_is_refused(client_with_paper):
    response = client_with_paper.post("/api/ask", json={"question": QUESTION, "paper_ids": ["000000000000"]},
                                      headers=HEADER)
    assert response.status_code == 404
    assert response.json() == {"kind": "unknown_paper", "paper_id": "000000000000"}


def test_a_malformed_body_is_an_invalid_request(client_with_paper):
    response = client_with_paper.post("/api/ask", json={"question": QUESTION, "k": "many"}, headers=HEADER)
    assert response.status_code == 422
    assert response.json() == {"kind": "invalid_request"}


def test_only_one_question_at_a_time(client_with_paper, scripted):
    lock = client_with_paper.app.state.paperpilot.question_lock
    assert lock.acquire(blocking=False)
    try:
        busy = client_with_paper.post("/api/ask", json={"question": QUESTION}, headers=HEADER)
    finally:
        lock.release()
    assert busy.status_code == 409 and busy.json() == {"kind": "busy_question"}
    scripted.add(REPLY, REPLY)
    assert ask_stream(client_with_paper, {"question": QUESTION})[2][-1][0] == "answer"
    assert ask_stream(client_with_paper, {"question": QUESTION})[2][-1][0] == "answer"
    assert not lock.locked()


def test_the_lock_is_released_after_a_failed_question(client_with_paper, scripted):
    scripted.add(RuntimeError("boom"))
    ask_stream(client_with_paper, {"question": QUESTION})
    assert not client_with_paper.app.state.paperpilot.question_lock.locked()


def test_the_lock_is_free_as_soon_as_the_answer_event_arrives(client_with_paper, scripted):
    """The worker releases the lock before sending the final event (no race with a quick follow-up)."""
    lock = client_with_paper.app.state.paperpilot.question_lock
    for _ in range(5):
        scripted.add(REPLY)
        with client_with_paper.stream("POST", "/api/ask", json={"question": QUESTION}, headers=HEADER) as response:
            for line in response.iter_lines():
                if line.startswith("event: answer"):
                    assert not lock.locked()
                    break
