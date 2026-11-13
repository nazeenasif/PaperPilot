"""Tests for paperpilot.llm (research R1–R4, ADR-0003). Offline: a scripted FakeClient only."""

import openai
import pytest

import fake_llm as f
from paperpilot import llm
from paperpilot.config import load_settings
from paperpilot.errors import LLMError, SettingsError

NOW = 1_800_000_000.0  # fixed "current time" in seconds for X-RateLimit-Reset maths


@pytest.fixture
def fake(monkeypatch, llm_env):
    """Install a FakeClient and record sleeps instead of sleeping; returns a setup function."""
    sleeps: list[float] = []
    monkeypatch.setattr(llm, "_sleep", sleeps.append)
    llm.reset_request_count()

    def install(*responses):
        client = f.FakeClient(list(responses))
        monkeypatch.setattr(llm, "_make_client", lambda settings: client)
        client.sleeps = sleeps
        return client

    return install


# --- the safety net itself ---


def test_real_client_is_blocked_in_tests():
    with pytest.raises(AssertionError, match="real LLM client"):
        openai.OpenAI(api_key="x")


# --- retry_wait: pure wait computation ---


def test_retry_after_header_wins():
    assert llm.retry_wait(f.rate_limited(retry_after="3"), attempt=1, now=NOW) == 3.0


def test_rate_limit_reset_header_in_epoch_ms():
    error = f.rate_limited(reset_ms=int((NOW + 10) * 1000))
    assert llm.retry_wait(error, attempt=1, now=NOW) == pytest.approx(10.0)


def test_reset_in_the_past_is_ignored_and_backoff_applies():
    # FR-023b: only a reset in the future (within 48 h) is trusted.
    assert llm.retry_wait(f.rate_limited(reset_ms=int((NOW - 5) * 1000)), attempt=1, now=NOW) == 2.0


def test_reset_beyond_48_hours_is_ignored():
    assert llm.retry_wait(f.rate_limited(reset_ms=int((NOW + 49 * 3600) * 1000)), attempt=1, now=NOW) == 2.0


def test_reset_given_in_seconds_is_ignored():
    # Read as milliseconds, a seconds value lands in 1970: ignored, never a huge or zero wait.
    assert llm.retry_wait(f.rate_limited(reset_ms=int(NOW + 30)), attempt=1, now=NOW) == 2.0


def test_reset_within_48_hours_is_used():
    assert llm.retry_wait(f.rate_limited(reset_ms=int((NOW + 30) * 1000)), attempt=1, now=NOW) == pytest.approx(30.0)


def test_requested_wait_is_not_capped():
    assert llm.requested_wait(f.rate_limited(retry_after="120"), now=NOW) == 120.0
    assert llm.requested_wait(f.rate_limited(reset_ms=int((NOW + 5 * 3600) * 1000)), now=NOW) == pytest.approx(18000.0)
    assert llm.requested_wait(f.rate_limited(), now=NOW) is None


def test_wait_is_capped_at_60_seconds():
    assert llm.retry_wait(f.rate_limited(retry_after="120"), attempt=1, now=NOW) == 60.0


@pytest.mark.parametrize(("attempt", "seconds"), [(1, 2.0), (2, 4.0), (3, 8.0)])
def test_backoff_without_headers(attempt, seconds):
    assert llm.retry_wait(f.rate_limited(), attempt=attempt, now=NOW) == seconds


@pytest.mark.parametrize("code", [408, 500, 502, 503, 504])
def test_transient_status_codes_are_retried(code):
    assert llm.retry_wait(f.status_error(code), attempt=1, now=NOW) == 2.0


@pytest.mark.parametrize("code", [400, 401, 402, 403, 404])
def test_permanent_status_codes_are_not_retried(code):
    assert llm.retry_wait(f.status_error(code), attempt=1, now=NOW) is None


def test_402_with_retry_after_is_retried():
    error = f.status_error(402, headers={"Retry-After": "5"})
    assert llm.retry_wait(error, attempt=1, now=NOW) == 5.0


def test_timeout_is_retried_with_backoff():
    assert llm.retry_wait(f.timeout(), attempt=1, now=NOW) == 2.0


# --- generate: the call, retries and reply checks ---


def test_normal_reply(fake):
    client = fake(f.ok("Answer [1].", prompt_tokens=11, completion_tokens=22, reasoning_tokens=5))
    reply = llm.generate("system rules", "the prompt")
    assert reply.text == "Answer [1]."
    assert (reply.input_tokens, reply.output_tokens, reply.reasoning_tokens) == (11, 22, 5)
    assert reply.attempts == 1
    assert reply.seconds >= 0
    assert llm.request_count() == 1
    call = client.calls[0]
    assert call["model"] == "test/model:free"
    assert call["messages"] == [
        {"role": "system", "content": "system rules"},
        {"role": "user", "content": "the prompt"},
    ]
    assert call["temperature"] == 0
    assert call["max_tokens"] == 2048
    assert "extra_body" not in call


def test_missing_usage_gives_none_tokens(fake):
    fake(f.no_usage("Answer [1]."))
    reply = llm.generate("s", "p")
    assert (reply.input_tokens, reply.output_tokens, reply.reasoning_tokens) == (None, None, None)


def test_reasoning_effort_is_sent_when_set(fake, monkeypatch):
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
    client = fake(f.ok("Answer [1]."))
    llm.generate("s", "p")
    assert client.calls[0]["extra_body"] == {"reasoning": {"effort": "low"}}


def test_rate_limit_then_success_waits_as_told(fake):
    client = fake(f.rate_limited(retry_after="3"), f.ok("Answer [1]."))
    reply = llm.generate("s", "p")
    assert reply.attempts == 2
    assert client.sleeps == [3.0]
    assert llm.request_count() == 2


def test_persistent_rate_limit_gives_readable_error(fake):
    client = fake(*[f.rate_limited() for _ in range(4)])
    with pytest.raises(LLMError) as error:
        llm.generate("s", "p")
    message = str(error.value)
    assert "rate limit" in message.lower()
    assert "Traceback" not in message
    assert "\n" not in message
    assert len(client.calls) == 4
    assert client.sleeps == [2.0, 4.0, 8.0]


def test_error_body_with_retryable_code_is_retried(fake):
    client = fake(f.error_body(502, "upstream down"), f.ok("Answer [1]."))
    assert llm.generate("s", "p").text == "Answer [1]."
    assert len(client.calls) == 2


def test_error_body_with_permanent_code_is_not_retried(fake):
    client = fake(f.error_body(400, "bad request"))
    with pytest.raises(LLMError):
        llm.generate("s", "p")
    assert len(client.calls) == 1


def test_length_finish_is_an_error_and_not_retried(fake):
    client = fake(f.length(reasoning_tokens=2000))
    with pytest.raises(LLMError) as error:
        llm.generate("s", "p")
    message = str(error.value)
    assert "reasoning" in message.lower()
    assert "LLM_REASONING_EFFORT" in message
    assert len(client.calls) == 1


def test_empty_content_is_an_error(fake):
    fake(f.ok(""))
    with pytest.raises(LLMError):
        llm.generate("s", "p")


def test_timeouts_then_success(fake):
    client = fake(f.timeout(), f.timeout(), f.ok("Answer [1]."))
    assert llm.generate("s", "p").attempts == 3
    assert client.sleeps == [2.0, 4.0]


def test_permanent_error_is_not_retried(fake):
    client = fake(f.status_error(404, "model not found"))
    with pytest.raises(LLMError):
        llm.generate("s", "p")
    assert len(client.calls) == 1


def test_api_key_is_scrubbed_from_errors(fake, llm_env):
    fake(f.status_error(401, f"Invalid key {llm_env} for this account"))
    with pytest.raises(LLMError) as error:
        llm.generate("s", "p")
    assert llm_env not in str(error.value)
    assert "***" in str(error.value)


def test_request_count_resets(fake):
    fake(f.ok("Answer [1]."))
    llm.generate("s", "p")
    llm.reset_request_count()
    assert llm.request_count() == 0
    assert llm.request_counts() == llm.RequestCounts(planned=0, retries=0)


def test_first_attempts_and_retries_are_counted_separately(fake):
    fake(f.rate_limited(retry_after="1"), f.ok("Answer [1]."), f.ok("Answer [2]."))
    llm.generate("s", "p")
    llm.generate("s", "p")
    counts = llm.request_counts()
    assert (counts.planned, counts.retries, counts.total) == (2, 1, 3)
    assert llm.request_count() == counts.total


def test_a_failed_call_counts_one_planned_request_and_its_retries(fake):
    fake(*[f.rate_limited(retry_after="1")] * llm.MAX_ATTEMPTS)
    with pytest.raises(LLMError):
        llm.generate("s", "p")
    assert llm.request_counts() == llm.RequestCounts(planned=1, retries=llm.MAX_ATTEMPTS - 1)


PROMPT = "SECRET-PROMPT-TEXT about the papers"


def retry_warnings(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == "paperpilot.llm" and r.levelname == "WARNING"]


@pytest.mark.parametrize(
    "error, reason, wait",
    [
        (f.rate_limited(retry_after="3"), "rate limited (HTTP 429)", 3.0),  # server's Retry-After
        (f.timeout(), "timeout", 2.0),  # first backoff step
        (f.error_body(503, "upstream overloaded"), "error in a 200 response (code 503)", 2.0),
        (f.status_error(502, "bad gateway"), "HTTP 502", 2.0),
    ],
)
def test_each_retry_is_logged_at_warning_with_attempt_reason_and_wait(fake, caplog, llm_env, error, reason, wait):
    client = fake(error, f.ok("Answer [1]."))
    with caplog.at_level("WARNING", logger="paperpilot.llm"):
        llm.generate("system rules", PROMPT)
    messages = retry_warnings(caplog)
    assert len(messages) == 1
    message = messages[0]
    assert "attempt 1 of 4" in message
    assert reason in message
    assert f"retrying in {wait:.1f} s" in message
    assert client.sleeps == [wait]
    for record in caplog.records:
        assert llm_env not in record.getMessage()
        assert PROMPT not in record.getMessage()


def test_every_retry_of_a_failing_call_is_logged(fake, caplog):
    fake(*[f.rate_limited(retry_after="1")] * llm.MAX_ATTEMPTS)
    with caplog.at_level("WARNING", logger="paperpilot.llm"):
        with pytest.raises(LLMError):
            llm.generate("s", PROMPT)
    messages = retry_warnings(caplog)
    assert [m.split(":")[0] for m in messages] == [
        f"LLM request attempt {n} of {llm.MAX_ATTEMPTS} failed" for n in range(1, llm.MAX_ATTEMPTS)
    ]


def test_a_first_try_success_logs_no_warning(fake, caplog):
    fake(f.ok("Answer [1]."))
    with caplog.at_level("WARNING", logger="paperpilot.llm"):
        llm.generate("s", PROMPT)
    assert retry_warnings(caplog) == []


def test_request_counts_subtract_for_a_part_of_a_run(fake):
    fake(f.ok("Answer [1]."), f.timeout(), f.ok("Answer [2]."))
    llm.generate("s", "p")
    before = llm.request_counts()
    llm.generate("s", "p")
    assert llm.request_counts() - before == llm.RequestCounts(planned=1, retries=1)


# --- settings checks happen before any client is created ---


def test_missing_api_key_is_a_settings_error(fake, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    with pytest.raises(SettingsError) as error:
        llm.generate("s", "p")
    assert "LLM_API_KEY" in str(error.value)


def test_unknown_provider_needs_a_base_url(fake, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "other")
    with pytest.raises(SettingsError) as error:
        llm.generate("s", "p")
    assert "LLM_BASE_URL" in str(error.value)


def test_client_is_built_without_sdk_retries(monkeypatch, llm_env):
    created = {}
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: created.update(kwargs) or object())
    llm._build_client(load_settings())
    assert created["api_key"] == llm_env
    assert created["base_url"] == "https://openrouter.ai/api/v1"
    assert created["max_retries"] == 0
    assert created["timeout"] == 60.0


# --- model listing (used by checkpoint 4; not a chat request) ---


def test_model_is_listed(monkeypatch, llm_env):
    client = f.FakeClient([], model_ids=["other/model:free", "test/model:free"])
    monkeypatch.setattr(llm, "_make_client", lambda settings: client)
    llm.reset_request_count()
    assert llm.model_is_listed() is True
    assert llm.request_count() == 0


def test_model_is_not_listed(monkeypatch, llm_env):
    client = f.FakeClient([], model_ids=["other/model:free"])
    monkeypatch.setattr(llm, "_make_client", lambda settings: client)
    assert llm.model_is_listed() is False


# --- per-request timeout (SC-008, research R13) ---


def test_client_uses_the_configured_timeout(monkeypatch, llm_env):
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "30")
    created = {}
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: created.update(kwargs) or object())
    llm._build_client(load_settings())
    assert created["timeout"] == 30.0


def test_persistent_timeouts_give_readable_error_naming_the_limit(fake):
    client = fake(*[f.timeout() for _ in range(4)])
    with pytest.raises(LLMError) as error:
        llm.generate("s", "p")
    message = str(error.value)
    assert "60 s" in message
    assert "LLM_TIMEOUT_SECONDS" in message
    assert "\n" not in message
    assert len(client.calls) == 4


# --- on_retry: retry waits reported to the caller (web app countdown, FR-023) ---


def test_on_retry_is_called_before_each_retry_wait(fake):
    client = fake(f.rate_limited(retry_after="3"), f.ok("Answer [1]."))
    events: list = client.sleeps  # the fake sleep appends to the same list, so order is visible
    llm.generate("s", "p", on_retry=events.append)
    notice, slept = events
    assert notice == llm.RetryNotice(attempt=1, max_attempts=4, wait_seconds=3.0, reason="rate_limited")
    assert slept == 3.0


@pytest.mark.parametrize(
    "error, reason",
    [
        (f.timeout(), "timeout"),
        (f.status_error(502, "bad gateway"), "server_error"),
        (f.error_body(503, "upstream overloaded"), "provider_error"),
    ],
)
def test_on_retry_reports_the_reason(fake, error, reason):
    fake(error, f.ok("Answer [1]."))
    notices: list = []
    llm.generate("s", "p", on_retry=notices.append)
    assert [n.reason for n in notices] == [reason]
    assert notices[0].attempt == 1 and notices[0].max_attempts == llm.MAX_ATTEMPTS


def test_on_retry_is_not_called_on_first_try_success(fake):
    fake(f.ok("Answer [1]."))
    notices: list = []
    llm.generate("s", "p", on_retry=notices.append)
    assert notices == []


def test_on_retry_is_not_called_for_the_final_failed_attempt(fake):
    fake(*[f.rate_limited(retry_after="1")] * llm.MAX_ATTEMPTS)
    notices: list = []
    with pytest.raises(LLMError):
        llm.generate("s", "p", on_retry=notices.append)
    assert [n.attempt for n in notices] == [1, 2, 3]


# --- long requested waits stop at once (FR-023a, ADR-0007) ---

from datetime import datetime, timedelta, timezone  # noqa: E402

from paperpilot.errors import RateLimitedError  # noqa: E402

CLOCK = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(llm, "_utcnow", lambda: CLOCK)
    monkeypatch.setattr(llm.time, "time", lambda: CLOCK.timestamp())
    return CLOCK


def test_a_wait_longer_than_the_cap_stops_after_one_request(fake, clock):
    client = fake(f.rate_limited(retry_after="120"), f.ok("never sent [1]."))
    with pytest.raises(RateLimitedError) as raised:
        llm.generate("s", "p")
    assert len(client.calls) == 1 and llm.request_counts().total == 1
    assert client.sleeps == []
    assert raised.value.until == CLOCK + timedelta(seconds=120)
    assert str(raised.value).startswith("rate limited until ")
    assert raised.value.reason == "rate_limited"


def test_a_wait_of_exactly_the_cap_is_retried(fake, clock):
    client = fake(f.rate_limited(retry_after="60"), f.ok("Answer [1]."))
    assert llm.generate("s", "p").text == "Answer [1]."
    assert client.sleeps == [60.0]


def daily_429(reset_seconds: float, limit: str) -> object:
    headers = {
        "X-RateLimit-Limit": limit,
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": str(int((CLOCK.timestamp() + reset_seconds) * 1000)),
    }
    return f.status_error(429, "Rate limit exceeded: free-models-per-day", headers=headers)


def test_a_daily_limit_429_is_marked_daily(fake, clock):
    fake(daily_429(5 * 3600, "50"))
    with pytest.raises(RateLimitedError) as raised:
        llm.generate("s", "p")
    assert raised.value.daily is True
    assert raised.value.until == CLOCK + timedelta(hours=5)
    assert llm.usage().used == llm.usage().limit  # the provider says the day is used up


def test_a_long_per_minute_wait_is_not_daily_unless_the_provider_says_so(fake, clock, monkeypatch):
    key_info = {"free_model_daily_requests": {"used": 30, "limit": 50, "remaining": 20}}
    monkeypatch.setattr(llm, "_fetch_key_info", lambda settings: key_info)
    fake(f.status_error(429, "slow down", headers={"X-RateLimit-Limit": "20", "Retry-After": "300"}))
    with pytest.raises(RateLimitedError) as raised:
        llm.generate("s", "p")
    assert raised.value.daily is False

    key_info["free_model_daily_requests"] = {"used": 50, "limit": 50, "remaining": 0}
    fake(f.status_error(429, "slow down", headers={"X-RateLimit-Limit": "20", "Retry-After": "300"}))
    with pytest.raises(RateLimitedError) as raised:
        llm.generate("s", "p")
    assert raised.value.daily is True


def test_the_retry_warning_shows_the_raw_reset_header(fake, clock, caplog):
    raw = str(int((CLOCK.timestamp() + 5) * 1000))
    fake(f.rate_limited(reset_ms=int(raw)), f.ok("Answer [1]."))
    with caplog.at_level("WARNING", logger="paperpilot.llm"):
        llm.generate("s", "p")
    assert any(f"X-RateLimit-Reset={raw}" in r.getMessage() for r in caplog.records)


# --- every terminal LLMError says why ---


@pytest.mark.parametrize(
    "responses, reason",
    [
        ([f.status_error(401, "bad key")], "bad_key"),
        ([f.status_error(403, "forbidden")], "bad_key"),
        ([f.status_error(402, "no credits")], "out_of_credits"),
        ([f.status_error(404, "no such model")], "unknown_model"),
        ([f.status_error(400, "bad request")], "bad_request"),
        ([f.rate_limited(retry_after="1")] * 4, "busy"),
        ([f.status_error(503, "down")] * 4, "busy"),
        ([f.timeout()] * 4, "timeout"),
        ([f.length()], "cut_off"),
        ([f.ok("   ")], "empty"),
    ],
)
def test_terminal_errors_carry_a_reason(fake, clock, responses, reason):
    fake(*responses)
    with pytest.raises(LLMError) as raised:
        llm.generate("s", "p")
    assert raised.value.reason == reason
