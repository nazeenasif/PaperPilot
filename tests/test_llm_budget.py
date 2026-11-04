"""Output budgets per task kind (research R5, ADR-0008): answers stay at 2048; summary sections,
the TL;DR and comparison rows get 4096, because reasoning counts against the limit. Fake client
only; no network."""

import pytest

import fake_llm as f
from paperpilot import llm, prompts, service
from paperpilot.errors import LLMError
from test_summarize import PromptReadingLLM

# OpenRouter's model list, 2026-11-04: max_completion_tokens of nvidia/nemotron-3-ultra-550b-a55b:free.
MODEL_MAX_COMPLETION_TOKENS = 65_536


@pytest.fixture
def client(monkeypatch, llm_env):
    monkeypatch.setattr(llm, "_sleep", lambda seconds: None)

    def install(*responses):
        fake = f.FakeClient(list(responses))
        monkeypatch.setattr(llm, "_make_client", lambda settings: fake)
        return fake

    return install


def test_answers_keep_2048_by_default(client):
    fake = client(f.ok("An answer [1]."))
    llm.generate("system", "prompt")
    assert fake.calls[0]["max_tokens"] == 2048


@pytest.mark.parametrize("task", ["summary_section", "tldr", "comparison"])
def test_summary_and_comparison_calls_get_4096(client, task):
    fake = client(f.ok("A part [1]."))
    llm.generate("system", "prompt", task=task)
    assert fake.calls[0]["max_tokens"] == 4096


def test_retries_keep_the_tasks_limit(client):
    fake = client(f.rate_limited(retry_after="1"), f.ok("A part [1]."))
    llm.generate("system", "prompt", task="tldr")
    assert [c["max_tokens"] for c in fake.calls] == [4096, 4096]


def test_an_unknown_task_sends_nothing(client):
    fake = client(f.ok("A part [1]."))
    with pytest.raises(ValueError, match="poem"):
        llm.generate("system", "prompt", task="poem")
    assert fake.calls == []
    assert llm.usage().used == 0


def test_every_budget_is_within_the_models_listed_maximum():
    assert llm.OUTPUT_TOKENS["answer"] == 2048
    assert all(limit <= MODEL_MAX_COMPLETION_TOKENS for limit in llm.OUTPUT_TOKENS.values())


@pytest.mark.parametrize(("task", "limit"), [("answer", "2048"), ("summary_section", "4096")])
def test_a_cut_off_message_names_the_limit_that_applied(client, task, limit):
    client(f.length())
    with pytest.raises(LLMError, match=limit) as raised:
        llm.generate("system", "prompt", task=task)
    assert raised.value.reason == "cut_off"


def test_summarize_asks_for_the_section_and_tldr_budgets(summary_env, monkeypatch):
    tasks = []
    fake = PromptReadingLLM()

    def generate(system, prompt, on_retry=None, task="answer"):
        tasks.append((system, task))
        return fake(system, prompt, on_retry)

    monkeypatch.setattr(llm, "generate", generate)
    service.summarize(summary_env.paper_id)
    assert tasks == [(prompts.SECTION_INSTRUCTION, "summary_section")] * 5 + [(prompts.TLDR_INSTRUCTION, "tldr")]


def test_ask_still_uses_the_answer_budget(answer_env, monkeypatch):
    seen = []

    def generate(system, prompt, on_retry=None, task="answer"):
        seen.append(task)
        return llm.LLMReply("Passages are searched by meaning [1].", 100, 40, None, 1, 0.01)

    monkeypatch.setattr(llm, "generate", generate)
    service.ask("How are papers searched?")
    assert seen == ["answer"]
