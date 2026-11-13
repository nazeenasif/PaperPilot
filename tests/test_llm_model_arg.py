"""`llm.generate(..., model=...)` and the task kind `judge` (Feature 5, contracts/engine-api.md):
the judge goes through the only LLM boundary, counted and retried as any request. Fake client
only; no network."""

import pytest

import fake_llm as f
from paperpilot import llm
from paperpilot.errors import LLMError

JUDGE = "google/gemma-4-31b-it:free"


@pytest.fixture
def client(monkeypatch, llm_env, library_env):
    monkeypatch.setattr(llm, "_sleep", lambda seconds: None)

    def install(*responses):
        fake = f.FakeClient(list(responses))
        monkeypatch.setattr(llm, "_make_client", lambda settings: fake)
        return fake

    return install


def test_a_model_argument_is_sent(client):
    fake = client(f.ok("A verdict."))
    llm.generate("system", "prompt", model=JUDGE)
    assert fake.calls[0]["model"] == JUDGE


def test_without_a_model_argument_the_configured_model_is_sent(client):
    fake = client(f.ok("An answer [1]."))
    llm.generate("system", "prompt")
    assert fake.calls[0]["model"] == "test/model:free"


def test_a_judge_request_is_counted_and_retried_like_any_other(client):
    fake = client(f.rate_limited(retry_after="1"), f.ok("A verdict."))
    before, used = llm.request_counts(), llm.usage().used
    llm.generate("system", "prompt", model=JUDGE, task="judge")
    assert [c["model"] for c in fake.calls] == [JUDGE, JUDGE]
    assert llm.request_counts() - before == llm.RequestCounts(1, 1)
    assert llm.usage().used == used + 2


def test_the_judge_has_its_own_output_limit():
    assert llm.OUTPUT_TOKENS["judge"] == 8192


def test_a_judge_request_uses_its_limit(client):
    fake = client(f.ok("A verdict."))
    llm.generate("system", "prompt", model=JUDGE, task="judge")
    assert fake.calls[0]["max_tokens"] == 8192


def test_a_cut_off_judge_reply_is_a_cut_off_with_its_tokens(client):
    client(f.length(reasoning_tokens=8192))
    with pytest.raises(LLMError) as raised:
        llm.generate("system", "prompt", model=JUDGE, task="judge")
    assert raised.value.reason == "cut_off" and raised.value.tokens["reasoning"] == 8192


def test_an_empty_model_argument_is_refused_before_anything_is_sent(client):
    fake = client(f.ok("A verdict."))
    with pytest.raises(ValueError):
        llm.generate("system", "prompt", model="  ")
    assert fake.calls == []
