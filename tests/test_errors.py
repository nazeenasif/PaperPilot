"""Tests for the error types added for the web app (contracts/engine-api.md)."""

from datetime import datetime, timezone

import pytest

from paperpilot.errors import (
    DailyLimitError,
    LLMError,
    PaperPilotError,
    PdfMissingError,
    RateLimitedError,
)

RESET = datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc)


def test_daily_limit_error_carries_usage_and_reset():
    error = DailyLimitError(used=50, limit=50, resets_at=RESET)
    assert isinstance(error, LLMError)
    assert (error.used, error.limit, error.resets_at) == (50, 50, RESET)
    assert "50" in str(error)
    assert error.resets_at.tzinfo is not None


def test_rate_limited_error_says_until_when():
    error = RateLimitedError(until=RESET, daily=True)
    assert isinstance(error, LLMError)
    assert str(error).startswith("rate limited until ")
    assert "2026-10-25T00:00:00" in str(error)
    assert (error.until, error.daily) == (RESET, True)


def test_rate_limited_error_defaults_to_not_daily():
    assert RateLimitedError(until=RESET).daily is False


def test_pdf_missing_error_names_the_paper():
    error = PdfMissingError("a8ca46b17146")
    assert isinstance(error, PaperPilotError)
    assert not isinstance(error, LLMError)
    assert error.paper_id == "a8ca46b17146"
    assert "a8ca46b17146" in str(error)


def test_llm_error_reason_defaults_to_none():
    assert LLMError("something failed").reason is None


@pytest.mark.parametrize(
    "reason",
    ["busy", "not_listed", "unknown_model", "bad_key", "out_of_credits", "cut_off", "empty", "timeout", "unreachable"],
)
def test_llm_error_accepts_a_reason(reason):
    error = LLMError("something failed", reason=reason)
    assert error.reason == reason
    assert str(error) == "something failed"


def test_llm_error_rejects_an_unknown_reason():
    with pytest.raises(ValueError):
        LLMError("x", reason="mystery")


def test_daily_and_rate_limit_errors_have_their_own_reasons():
    assert DailyLimitError(used=50, limit=50, resets_at=RESET).reason == "daily_limit"
    assert RateLimitedError(until=RESET).reason == "rate_limited"
