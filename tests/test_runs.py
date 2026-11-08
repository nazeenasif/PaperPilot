"""Run control for summaries and comparisons: the pre-check, accounting and stop rules (spec US5,
FR-021-FR-024; research R8; ADR-0009). Fake client and scripted models only; no network."""

from datetime import datetime, timedelta, timezone

import pytest

import fake_llm as f
from paperpilot import library, llm, prompts, service
from paperpilot.errors import DailyLimitError, LLMError, RateLimitedError
from paperpilot.llm import generate as real_generate
from test_compare import RowLLM
from test_summarize import PromptReadingLLM

FACETS = ["problem", "method", "data", "results", "limitations"]
RESETS = datetime(2026, 11, 9, tzinfo=timezone.utc)
UNTIL = datetime.now(timezone.utc) + timedelta(hours=2)


@pytest.fixture
def client(monkeypatch, summary_env):
    """The real llm.generate over a fake client, so the shared counters move."""
    monkeypatch.setattr(llm, "generate", real_generate)
    monkeypatch.setattr(llm, "_sleep", lambda seconds: None)

    def install(*responses):
        fake = f.FakeClient(list(responses))
        monkeypatch.setattr(llm, "_make_client", lambda settings: fake)
        return fake

    return install


class StopsAt(PromptReadingLLM):
    """Raises the given error on the nth call, and fails the test if called again."""

    def __init__(self, nth, error):
        super().__init__()
        self.nth, self.error = nth, error

    def __call__(self, system, prompt, on_retry=None, task="answer"):
        if len(self.calls) == self.nth - 1:
            self.calls.append((system, prompt))
            raise self.error
        assert len(self.calls) < self.nth, "a request was sent after the run should have stopped"
        return super().__call__(system, prompt, on_retry, task)


def states(summary):
    return [p.state for p in [*summary.sections, summary.tldr]]


# --- pre-check (FR-023) ---


def test_a_summary_with_too_few_requests_left_sends_nothing(client, summary_env, monkeypatch):
    fake = client(f.ok("A part [1]."))
    monkeypatch.setenv("DAILY_REQUEST_LIMIT", "10")
    for _ in range(5):
        llm.count_request()
    with pytest.raises(DailyLimitError) as raised:
        service.summarize(summary_env.paper_id)
    assert fake.calls == [] and raised.value.needed == 6 and raised.value.used == 5


def test_a_summary_with_exactly_enough_requests_runs(client, summary_env, monkeypatch):
    client(*[f.ok("A part [1].") for _ in range(6)])
    monkeypatch.setenv("DAILY_REQUEST_LIMIT", "10")
    for _ in range(4):
        llm.count_request()
    assert service.summarize(summary_env.paper_id).requests["planned"] == 6


def test_a_saved_summary_opens_with_no_requests_left(summary_env, monkeypatch):
    monkeypatch.setattr(llm, "generate", PromptReadingLLM())
    first = service.summarize(summary_env.paper_id)
    monkeypatch.setenv("DAILY_REQUEST_LIMIT", "1")
    llm.count_request()
    assert service.summarize(summary_env.paper_id).created_at == first.created_at


def test_a_part_retry_needs_only_its_own_plan(summary_env, monkeypatch):
    fake = PromptReadingLLM()
    monkeypatch.setattr(llm, "generate", fake)
    service.summarize(summary_env.paper_id)
    monkeypatch.setenv("DAILY_REQUEST_LIMIT", "1")
    assert service.summarize(summary_env.paper_id, retry_parts=["results"]).requests["planned"] == 1
    llm.count_request()
    with pytest.raises(DailyLimitError) as raised:
        service.summarize(summary_env.paper_id, retry_parts=["results"])
    assert raised.value.needed == 1


def test_a_comparison_with_too_few_requests_left_sends_nothing(summary_env, second_paper, monkeypatch):
    fake = RowLLM()
    monkeypatch.setattr(llm, "generate", fake)
    second = library.add_paper(second_paper).paper_id
    monkeypatch.setenv("DAILY_REQUEST_LIMIT", "4")
    llm.count_request()
    with pytest.raises(DailyLimitError) as raised:
        service.compare([summary_env.paper_id, second], list(prompts.ASPECTS))
    assert fake.calls == [] and raised.value.needed == 5


# --- accounting (FR-022) ---


def test_retries_are_counted_apart_and_in_the_shared_usage(client, summary_env):
    client(f.rate_limited(retry_after="1"), *[f.ok("A part [1].") for _ in range(6)])
    before = llm.usage().used
    summary = service.summarize(summary_env.paper_id)
    assert summary.requests == {"planned": 6, "retries": 1}
    assert llm.usage().used == before + 7


def test_first_attempts_never_exceed_the_plan(client, summary_env):
    fake = client(*[f.ok("A part [1].") for _ in range(6)])
    plan = service.summary_plan(summary_env.paper_id)["max_requests"]
    assert service.summarize(summary_env.paper_id).requests["planned"] <= plan and len(fake.calls) == plan


# --- stop rules (FR-024) ---


@pytest.mark.parametrize(
    ("error", "reason", "until"),
    [
        (DailyLimitError(50, 50, RESETS), "daily_limit", RESETS.isoformat()),
        (RateLimitedError(UNTIL), "rate_limited", UNTIL.isoformat()),
        (LLMError("busy", reason="busy"), "busy", None),
        (LLMError("timed out", reason="timeout"), "timeout", None),
        (LLMError("bad key", reason="bad_key"), "bad_key", None),
    ],
    ids=["daily limit", "long wait", "busy", "timeout", "bad key"],
)
def test_a_systemic_failure_stops_the_run_and_keeps_finished_parts(summary_env, monkeypatch, error, reason, until):
    fake = StopsAt(3, error)
    monkeypatch.setattr(llm, "generate", fake)
    summary = service.summarize(summary_env.paper_id)
    assert states(summary) == ["verified", "verified", "not_started", "not_started", "not_started", "not_started"]
    stopped = [p for p in [*summary.sections, summary.tldr] if p.state == "not_started"]
    assert {p.reason for p in stopped} == {reason} and {p.until for p in stopped} == {until}
    assert len(fake.calls) == 3
    assert states(service.saved_summary(summary_env.paper_id)) == states(summary)


def test_a_cut_off_does_not_stop_the_run(summary_env, monkeypatch):
    fake = StopsAt(3, LLMError("cut off", reason="cut_off"))
    fake.nth = 3

    class CutOffOnce(PromptReadingLLM):
        def __call__(self, system, prompt, on_retry=None, task="answer"):
            if "Section: Data." in prompt:
                raise LLMError("cut off", reason="cut_off")
            return super().__call__(system, prompt, on_retry, task)

    monkeypatch.setattr(llm, "generate", CutOffOnce())
    assert states(service.summarize(summary_env.paper_id)) == ["verified", "verified", "failed", "verified", "verified", "verified"]


def test_a_stop_on_the_tldr_keeps_the_sections(summary_env, monkeypatch):
    monkeypatch.setattr(llm, "generate", StopsAt(6, DailyLimitError(50, 50, RESETS)))
    summary = service.summarize(summary_env.paper_id)
    assert all(s.state == "verified" for s in summary.sections)
    assert (summary.tldr.state, summary.tldr.reason) == ("not_started", "daily_limit")


def test_a_stop_before_anything_finished_raises_and_saves_nothing(summary_env, monkeypatch):
    monkeypatch.setattr(llm, "generate", StopsAt(1, LLMError("bad key", reason="bad_key")))
    with pytest.raises(LLMError):
        service.summarize(summary_env.paper_id)
    assert service.saved_summary(summary_env.paper_id) is None


def test_stopped_parts_can_be_retried_later(summary_env, monkeypatch):
    monkeypatch.setattr(llm, "generate", StopsAt(3, DailyLimitError(50, 50, RESETS)))
    stopped = service.summarize(summary_env.paper_id)
    fake = PromptReadingLLM()
    monkeypatch.setattr(llm, "generate", fake)
    done = service.summarize(summary_env.paper_id, retry_parts=["data", "results", "limitations", "tldr"])
    assert len(fake.calls) == 4 and all(p.state == "verified" for p in [*done.sections, done.tldr])
    assert done.sections[:2] == stopped.sections[:2]


def test_a_stopped_regeneration_keeps_the_complete_summary(summary_env, monkeypatch):
    monkeypatch.setattr(llm, "generate", PromptReadingLLM())
    first = service.summarize(summary_env.paper_id)
    monkeypatch.setattr(llm, "generate", StopsAt(3, DailyLimitError(50, 50, RESETS)))
    kept = service.summarize(summary_env.paper_id, regenerate=True)
    assert kept.sections == first.sections
    assert kept.pending["retry_parts"] == ["data", "results", "limitations", "tldr"]


def test_a_comparison_stops_the_same_way(summary_env, second_paper, monkeypatch):
    second = library.add_paper(second_paper).paper_id

    class Stops(RowLLM):
        def __call__(self, system, prompt, on_retry=None, task="answer"):
            if "Row: Results." in prompt:
                self.calls.append((system, prompt, task))
                raise DailyLimitError(50, 50, RESETS)
            assert "Row: Limitations." not in prompt, "a request was sent after the run should have stopped"
            return super().__call__(system, prompt, on_retry, task)

    monkeypatch.setattr(llm, "generate", Stops())
    comparison = service.compare([summary_env.paper_id, second], ["method", "results", "limitations"])
    assert [(r.aspect, r.state, r.reason) for r in comparison.rows] == [
        ("method", "ok", None), ("results", "not_started", "daily_limit"), ("limitations", "not_started", "daily_limit"),
    ]
    assert comparison.rows[1].until == RESETS.isoformat()
    assert service.saved_comparison([summary_env.paper_id, second], ["method", "results", "limitations"]).rows == comparison.rows


def test_a_comparison_stopped_before_anything_finished_raises(summary_env, second_paper, monkeypatch):
    second = library.add_paper(second_paper).paper_id

    def stops(system, prompt, on_retry=None, task="answer"):
        raise LLMError("busy", reason="busy")

    monkeypatch.setattr(llm, "generate", stops)
    with pytest.raises(LLMError):
        service.compare([summary_env.paper_id, second], ["method"])
    assert service.saved_comparison([summary_env.paper_id, second], ["method"]) is None


# --- events ---


def test_retry_waits_name_the_part_being_retried(client, summary_env):
    client(f.ok("A part [1]."), f.rate_limited(retry_after="1"), *[f.ok("A part [1].") for _ in range(5)])
    events = []
    service.summarize(summary_env.paper_id, on_event=lambda kind, detail: events.append((kind, detail)))
    waits = [detail for kind, detail in events if kind == "retry_wait"]
    assert [w["part"] for w in waits] == ["method"] and waits[0]["attempt"] == 1


def test_not_started_parts_are_sent_as_events(summary_env, monkeypatch):
    monkeypatch.setattr(llm, "generate", StopsAt(5, DailyLimitError(50, 50, RESETS)))
    events = []
    service.summarize(summary_env.paper_id, on_event=lambda kind, detail: events.append((kind, detail)))
    parts = {d["part"]: d["state"] for k, d in events if k == "part"}
    assert parts["limitations"] == "not_started" and parts["tldr"] == "not_started"
