"""Tests for paperpilot.service.ask (contracts/answer-api.md). Offline: scripted LLM, fake embedder."""

import pytest

from paperpilot import prompts
from paperpilot.errors import EmptyQueryError
from paperpilot.llm import LLMReply
from paperpilot.service import Answer, ask

QUESTION = "Which evaluation dataset was used?"


# --- US1: a cited answer with its passages ---


def test_answer_with_numbered_passages(answer_env, fake_answers):
    fake_answers.add("The system is evaluated on a benchmark dataset of questions [1].")
    answer = ask(QUESTION)
    assert isinstance(answer, Answer)
    assert answer.text == "The system is evaluated on a benchmark dataset of questions [1]."
    assert answer.not_found is False
    assert [p.number for p in answer.passages] == list(range(1, len(answer.passages) + 1))
    for p in answer.passages:
        assert p.paper_id == answer_env.paper_id
        assert p.title == answer_env.title
        assert p.section and p.page >= 1 and p.text
        assert 0.0 <= p.score <= 1.0
    assert answer.citations.valid == [1]
    assert answer.citations.invalid == []


def test_answer_metadata(answer_env, fake_answers):
    fake_answers.add("Evaluated on a benchmark dataset [1].")
    answer = ask(QUESTION)
    assert answer.question == QUESTION
    assert answer.standalone_question == QUESTION
    assert answer.rewrite_applied is False
    assert answer.fallback_reason is None
    assert answer.rewrite_fallback_reason is None
    assert answer.warning is None
    assert answer.rejected_answer is None
    assert answer.llm_calls == 1
    assert set(answer.timings) == {"rewrite", "retrieve", "generate"}
    assert answer.timings["rewrite"] == 0.0
    assert answer.tokens == {"input": 100, "output": 40}
    assert answer.word_count == prompts.word_count(answer.text)


def test_token_keys_omitted_when_provider_reports_none(answer_env, fake_answers):
    fake_answers.add(LLMReply("Evaluated on a benchmark [1].", None, None, None, 1, 0.01))
    assert ask(QUESTION).tokens == {}


def test_reasoning_tokens_reported_when_present(answer_env, fake_answers):
    fake_answers.add(LLMReply("Evaluated on a benchmark [1].", 100, 300, 250, 1, 0.01))
    assert ask(QUESTION).tokens == {"input": 100, "output": 300, "reasoning": 250}


def test_prompt_contains_passages_and_question(answer_env, fake_answers):
    fake_answers.add("Evaluated on a benchmark [1].")
    answer = ask(QUESTION)
    system, prompt = fake_answers.calls[0]
    assert system == prompts.SYSTEM_INSTRUCTION
    for p in answer.passages:
        assert f'<passage id="{p.number}"' in prompt
    assert prompt.rstrip().endswith(f"Question: {QUESTION}")


def test_k_limits_the_passages_sent(answer_env, fake_answers):
    fake_answers.add("Evaluated on a benchmark [1].")
    answer = ask(QUESTION, k=2)
    assert len(answer.passages) <= 2
    assert '<passage id="3"' not in fake_answers.calls[0][1]


def test_long_answer_is_returned_whole(answer_env, fake_answers):
    long_reply = " ".join(["The benchmark dataset is described here [1]."] * 57)  # about 400 words
    fake_answers.add(long_reply)
    answer = ask(QUESTION)
    assert answer.text == long_reply
    assert answer.word_count > 300


@pytest.mark.parametrize("question", ["", "   ", "\n\t"])
def test_empty_question_is_rejected_without_a_call(answer_env, fake_answers, question):
    with pytest.raises(EmptyQueryError):
        ask(question)
    assert fake_answers.calls == []
