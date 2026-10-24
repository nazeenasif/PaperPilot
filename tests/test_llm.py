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


def test_reset_in_the_past_waits_zero():
    assert llm.retry_wait(f.rate_limited(reset_ms=int((NOW - 5) * 1000)), attempt=1, now=NOW) == 0.0


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
