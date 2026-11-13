"""ask() progress events for the web app (spec FR-006, contracts/engine-api.md)."""

from paperpilot import prompts
from paperpilot.service import Turn, ask

QUESTION = "Which evaluation dataset was used?"
REPLY = "Evaluated on a benchmark dataset [1]."


def recorder():
    events: list[tuple[str, dict]] = []
    return events, lambda kind, detail: events.append((kind, detail))


def test_plain_question_reports_searching_reading_generating_checking(answer_env, fake_answers):
    fake_answers.add(REPLY)
    events, on_event = recorder()
    answer = ask(QUESTION, on_event=on_event)
    assert [kind for kind, _ in events] == ["searching", "reading", "generating", "checking"]
    reading = dict(events)["reading"]
    assert reading == {"passages": len(answer.passages), "papers": 1}


def test_follow_up_reports_rewriting_first(answer_env, fake_answers):
    fake_answers.add("Which evaluation dataset does the benchmark use?", REPLY)
    events, on_event = recorder()
    ask("Which dataset does it use?", history=[Turn("user", QUESTION), Turn("assistant", REPLY)], on_event=on_event)
    assert [kind for kind, _ in events] == ["rewriting", "searching", "reading", "generating", "checking"]


def test_below_threshold_reports_only_searching(answer_env, fake_answers, monkeypatch):
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "0.99")
    events, on_event = recorder()
    answer = ask(QUESTION, on_event=on_event)
    assert answer.fallback_reason == "below_threshold"
    assert [kind for kind, _ in events] == ["searching"]
    assert fake_answers.calls == []


def test_empty_library_reports_only_searching(library_env, fake_embedder, llm_env, fake_answers, monkeypatch):
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "0.0")
    events, on_event = recorder()
    answer = ask(QUESTION, on_event=on_event)
    assert answer.fallback_reason == "no_passages"
    assert [kind for kind, _ in events] == ["searching"]


def test_retry_waits_are_forwarded_as_events(answer_env, fake_answers):
    from paperpilot.llm import RetryNotice

    fake_answers.add(RetryNotice(attempt=1, max_attempts=4, wait_seconds=3.0, reason="rate_limited"), REPLY)
    events, on_event = recorder()
    ask(QUESTION, on_event=on_event)
    assert [kind for kind, _ in events] == ["searching", "reading", "generating", "retry_wait", "checking"]
    assert dict(events)["retry_wait"] == {"attempt": 1, "max_attempts": 4, "wait_seconds": 3.0, "reason": "rate_limited"}


def test_events_never_carry_answer_or_passage_text(answer_env, fake_answers):
    fake_answers.add(REPLY)
    events, on_event = recorder()
    answer = ask(QUESTION, on_event=on_event)
    flat = repr(events)
    assert REPLY not in flat
    assert all(p.text[:40] not in flat for p in answer.passages)


def test_without_on_event_ask_behaves_as_before(answer_env, fake_answers):
    fake_answers.add(REPLY)
    answer = ask(QUESTION)
    assert answer.text == REPLY
    assert answer.not_found is False


def test_not_found_reply_still_reports_checking(answer_env, fake_answers):
    fake_answers.add(prompts.NOT_FOUND)
    events, on_event = recorder()
    answer = ask(QUESTION, on_event=on_event)
    assert answer.fallback_reason == "model_not_found"
    assert [kind for kind, _ in events][-1] == "checking"
