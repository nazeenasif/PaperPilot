"""Shared daily request counter and the provider's own figure (spec FR-024–FR-026, ADR-0007).

No network: the key endpoint is replaced by a stub (an autouse guard blocks the real one).
"""

import multiprocessing
import os
import sqlite3
import threading
from datetime import datetime, timezone

import pytest

import fake_llm as f
from paperpilot import llm
from paperpilot.errors import DailyLimitError

DAY = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
NEXT_DAY = datetime(2026, 10, 26, 0, 30, tzinfo=timezone.utc)


@pytest.fixture
def usage_env(library_env, llm_env, monkeypatch):
    """A temporary library (where usage.sqlite3 lives), a fixed clock and no real sleeps."""
    monkeypatch.setattr(llm, "_utcnow", lambda: DAY)
    monkeypatch.setattr(llm, "_sleep", lambda seconds: None)
    llm.reset_request_count()
    return library_env


@pytest.fixture
def fake(monkeypatch, usage_env):
    def install(*responses):
        client = f.FakeClient(list(responses))
        monkeypatch.setattr(llm, "_make_client", lambda settings: client)
        return client

    return install


def stored_rows(library_dir):
    with sqlite3.connect(library_dir / "usage.sqlite3") as db:
        return db.execute("SELECT day, used, request_limit, source FROM daily_usage ORDER BY day").fetchall()


# --- counting ---


def test_every_attempt_is_counted_in_the_shared_database(fake, usage_env):
    fake(f.rate_limited(retry_after="1"), f.ok("A [1]."), f.ok("B [1]."))
    llm.generate("s", "p")
    llm.generate("s", "p")
    assert stored_rows(usage_env) == [("2026-10-25", 3, 50, "local")]
    usage = llm.usage()
    assert (usage.used, usage.limit, usage.remaining, usage.source) == (3, 50, 47, "local")


def test_a_new_utc_day_starts_from_zero(fake, usage_env, monkeypatch):
    fake(f.ok("A [1]."), f.ok("B [1]."))
    llm.generate("s", "p")
    monkeypatch.setattr(llm, "_utcnow", lambda: NEXT_DAY)
    assert llm.usage().used == 0
    llm.generate("s", "p")
    assert [row[:2] for row in stored_rows(usage_env)] == [("2026-10-25", 1), ("2026-10-26", 1)]


def test_usage_resets_at_the_next_utc_midnight(usage_env):
    assert llm.usage().resets_at == datetime(2026, 10, 26, 0, 0, tzinfo=timezone.utc)


def test_the_limit_comes_from_the_setting_until_the_provider_reports_one(usage_env, monkeypatch):
    monkeypatch.setenv("DAILY_REQUEST_LIMIT", "1000")
    assert llm.usage().limit == 1000


def test_concurrent_threads_never_lose_counts(usage_env):
    def work():
        for _ in range(5):
            llm.count_request()

    threads = [threading.Thread(target=work) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert llm.usage().used == 100


def count_in_another_process(library_dir: str, times: int) -> None:
    """Runs in a spawned process: count `times` requests against the same database."""
    os.environ["LIBRARY_DIR"] = library_dir
    from paperpilot import llm as child_llm

    child_llm._utcnow = lambda: DAY
    for _ in range(times):
        child_llm.count_request()


def test_two_processes_never_lose_counts(usage_env):
    context = multiprocessing.get_context("spawn")
    processes = [context.Process(target=count_in_another_process, args=(str(usage_env), 25)) for _ in range(2)]
    for p in processes:
        p.start()
    for p in processes:
        p.join(timeout=120)
        assert p.exitcode == 0
    assert llm.usage().used == 50


# --- the daily pre-check ---


def test_at_the_limit_no_request_is_sent(fake, usage_env, monkeypatch):
    monkeypatch.setenv("DAILY_REQUEST_LIMIT", "2")
    client = fake(f.ok("A [1]."), f.ok("B [1]."), f.ok("C [1]."))
    llm.generate("s", "p")
    llm.generate("s", "p")
    with pytest.raises(DailyLimitError) as raised:
        llm.generate("s", "p")
    assert len(client.calls) == 2
    assert (raised.value.used, raised.value.limit) == (2, 2)
    assert raised.value.resets_at == datetime(2026, 10, 26, tzinfo=timezone.utc)
    assert llm.request_counts().total == 2


# --- the provider's figure ---


def test_refresh_adopts_the_providers_figure(usage_env, monkeypatch):
    monkeypatch.setattr(llm, "_fetch_key_info", lambda settings: {
        "is_free_tier": True, "free_model_daily_requests": {"used": 34, "limit": 50, "remaining": 16}})
    llm.count_request()
    usage = llm.refresh_usage()
    assert (usage.used, usage.limit, usage.remaining, usage.source) == (34, 50, 16, "provider")
    assert llm.usage().used == 34
    llm.count_request()
    assert llm.usage().used == 35  # local counting continues from the provider's figure


def test_refresh_keeps_the_local_count_when_the_provider_cannot_be_read(usage_env, monkeypatch):
    def broken(settings):
        raise OSError("network down")

    monkeypatch.setattr(llm, "_fetch_key_info", broken)
    llm.count_request()
    usage = llm.refresh_usage()
    assert (usage.used, usage.source) == (1, "local")


def test_refresh_skips_the_key_endpoint_for_other_providers(usage_env, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    calls = []
    monkeypatch.setattr(llm, "_fetch_key_info", lambda settings: calls.append(settings))
    assert llm.refresh_usage().source == "local"
    assert calls == []


def test_the_key_endpoint_is_blocked_in_tests(usage_env):
    """The autouse guard: a test that forgets to stub it fails instead of calling OpenRouter."""
    with pytest.raises(AssertionError, match="key endpoint"):
        llm._fetch_key_info(None)
