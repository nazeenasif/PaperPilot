"""Tests for the checkpoint request budget (scripts/request_budget.py). Offline: FakeClient only."""

import sys
from pathlib import Path

import pytest

import fake_llm as f
from paperpilot import llm
from paperpilot.errors import LLMError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from request_budget import SAFETY_FACTOR, budget_checks  # noqa: E402


@pytest.fixture
def fake(monkeypatch, llm_env):
    """Install a FakeClient with the given responses; sleeps are skipped."""
    monkeypatch.setattr(llm, "_sleep", lambda seconds: None)
    llm.reset_request_count()

    def install(*responses):
        client = f.FakeClient(list(responses))
        monkeypatch.setattr(llm, "_make_client", lambda settings: client)
        return client

    return install


def passed(checks):
    return all(ok for ok, _ in checks)


def test_a_run_with_one_retry_passes(fake):
    fake(f.ok("A [1]."), f.rate_limited(retry_after="1"), f.ok("B [1]."))
    llm.generate("s", "p")
    llm.generate("s", "p")
    checks = budget_checks("run", llm.request_counts(), plan=2)
    assert passed(checks)
    assert any("1 retry" in text for _, text in checks)


def test_an_unplanned_extra_call_fails(fake):
    fake(f.ok("A [1]."), f.ok("B [1]."), f.ok("C [1]."))
    for _ in range(3):
        llm.generate("s", "p")
    checks = budget_checks("run", llm.request_counts(), plan=2)
    assert not passed(checks)
    failed = [text for ok, text in checks if not ok]
    assert len(failed) == 1 and "3 planned" in failed[0] and "plan 2" in failed[0]


def test_retries_beyond_the_safety_cap_fail(fake):
    fake(f.rate_limited(retry_after="1"), f.rate_limited(retry_after="1"), f.ok("A [1]."))
    llm.generate("s", "p")
    counts = llm.request_counts()
    assert counts.total > SAFETY_FACTOR * 1
    checks = budget_checks("run", counts, plan=1)
    failed = [text for ok, text in checks if not ok]
    assert len(failed) == 1 and "safety cap 2" in failed[0]


def test_retries_up_to_the_safety_cap_pass(fake):
    fake(f.rate_limited(retry_after="1"), f.ok("A [1]."), f.rate_limited(retry_after="1"), f.ok("B [1]."))
    llm.generate("s", "p")
    llm.generate("s", "p")
    counts = llm.request_counts()
    assert counts.total == SAFETY_FACTOR * 2
    assert passed(budget_checks("run", counts, plan=2))


def test_a_failed_call_still_counts_as_one_planned_request(fake):
    fake(*[f.rate_limited(retry_after="1")] * llm.MAX_ATTEMPTS)
    with pytest.raises(LLMError):
        llm.generate("s", "p")
    checks = budget_checks("run", llm.request_counts(), plan=1)
    assert checks[0][0] is True  # planned 1 of 1
    assert checks[1][0] is False  # 4 requests > cap 2


def test_a_zero_plan_fails_on_any_request(fake):
    fake(f.ok("A [1]."))
    llm.generate("s", "p")
    assert not passed(budget_checks("offline part", llm.request_counts(), plan=0))
    llm.reset_request_count()
    assert passed(budget_checks("offline part", llm.request_counts(), plan=0))
