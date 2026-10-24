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


# --- US2: unsupported questions get the not-found sentence ---


def test_all_passages_below_threshold_gives_not_found_without_a_call(answer_env, fake_answers, monkeypatch):
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "0.99")
    answer = ask(QUESTION)
    assert answer.text == prompts.NOT_FOUND
    assert answer.not_found is True
    assert answer.passages == []
    assert answer.llm_calls == 0
    assert answer.fallback_reason == "below_threshold"
    assert answer.citations.valid == [] and answer.citations.invalid == []
    assert fake_answers.calls == []


def test_threshold_gates_on_the_top_score_and_sends_all_k_passages(answer_env, fake_answers, monkeypatch):
    # The threshold was calibrated on top-1 scores, so it gates the question, not each passage.
    from paperpilot.library import search

    results = search(QUESTION)
    top = max(r.score for r in results)
    assert any(r.score < top for r in results), "the test needs passages below the top score"
    monkeypatch.setenv("RELEVANCE_THRESHOLD", str(top))
    fake_answers.add("Evaluated on a benchmark [1].")
    answer = ask(QUESTION)
    assert answer.fallback_reason is None
    assert [p.passage_id for p in answer.passages] == [r.passage_id for r in results]
    assert [p.number for p in answer.passages] == list(range(1, len(results) + 1))
    _, prompt = fake_answers.calls[0]
    assert all(f'<passage id="{n}"' in prompt for n in range(1, len(results) + 1))


def test_top_score_just_below_threshold_gives_not_found_without_a_call(answer_env, fake_answers, monkeypatch):
    from paperpilot.library import search

    top = max(r.score for r in search(QUESTION))
    monkeypatch.setenv("RELEVANCE_THRESHOLD", str(min(1.0, top + 0.001)))
    answer = ask(QUESTION)
    assert answer.fallback_reason == "below_threshold"
    assert answer.passages == []
    assert fake_answers.calls == []


def test_model_not_found_reply_becomes_the_exact_sentence(answer_env, fake_answers):
    quoted_without_period = '"' + prompts.NOT_FOUND.rstrip(".") + '"'
    fake_answers.add(quoted_without_period)
    answer = ask(QUESTION)
    assert answer.text == prompts.NOT_FOUND
    assert answer.not_found is True
    assert answer.fallback_reason == "model_not_found"
    assert answer.warning is None
    assert answer.llm_calls == 1


def test_empty_library_gives_not_found_without_a_call(library_env, fake_embedder, llm_env, fake_answers, monkeypatch):
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "0.0")
    answer = ask(QUESTION)
    assert answer.text == prompts.NOT_FOUND
    assert answer.passages == []
    assert answer.llm_calls == 0
    assert answer.fallback_reason == "no_passages"
    assert fake_answers.calls == []


# --- US3: ask within selected papers ---


@pytest.fixture
def two_papers(answer_env, tmp_path, make_pdf):
    """The answer_env paper plus a second, different paper; returns both IDs."""
    from paperpilot.library import add_paper

    second = add_paper(make_pdf(tmp_path / "second.pdf", title="A Second Paper on Searching Research"))
    return answer_env.paper_id, second.paper_id


def test_filtered_question_uses_only_the_selected_paper(two_papers, fake_answers):
    _, second = two_papers
    fake_answers.add("Evaluated on a benchmark [1].")
    answer = ask(QUESTION, paper_ids=[second])
    assert answer.passages
    assert {p.paper_id for p in answer.passages} == {second}
    prompt = fake_answers.calls[0][1]
    assert 'title="A Second Paper on Searching Research"' in prompt
    assert "A Study of Searching Research Papers by Meaning" not in prompt  # the other paper's title


def test_unknown_paper_is_rejected_before_any_call(two_papers, fake_answers):
    from paperpilot.errors import UnknownPaperError

    with pytest.raises(UnknownPaperError):
        ask(QUESTION, paper_ids=["000000000000"])
    assert fake_answers.calls == []


def test_empty_filter_searches_the_whole_library(two_papers, fake_answers):
    fake_answers.add("Evaluated on a benchmark [1].", "Evaluated on a benchmark [1].")
    unfiltered = ask(QUESTION, k=20)
    empty_filter = ask(QUESTION, k=20, paper_ids=[])
    assert [p.passage_id for p in empty_filter.passages] == [p.passage_id for p in unfiltered.passages]
    assert {p.paper_id for p in unfiltered.passages} == set(two_papers)


# --- US4: follow-up questions ---



@pytest.fixture
def history():
    from paperpilot.service import Turn

    return [Turn("user", "What is the evaluation setup?"), Turn("assistant", "A benchmark dataset is used [1].")]


@pytest.fixture
def search_spy(monkeypatch):
    """Record every query sent to library.search, still running the real search."""
    from paperpilot import library

    queries: list[str] = []
    real_search = library.search

    def spy(query, *args, **kwargs):
        queries.append(query)
        return real_search(query, *args, **kwargs)

    monkeypatch.setattr(library, "search", spy)
    return queries


def test_no_history_means_no_rewrite_call(answer_env, fake_answers):
    fake_answers.add("Evaluated on a benchmark [1].")
    answer = ask(QUESTION)
    assert answer.llm_calls == 1
    assert fake_answers.calls[0][0] == prompts.SYSTEM_INSTRUCTION
    assert answer.rewrite_applied is False
    assert answer.rewrite_fallback_reason is None


def test_follow_up_is_rewritten_and_used_for_search(answer_env, fake_answers, history, search_spy):
    standalone = "Which evaluation dataset does the benchmark use?"
    fake_answers.add(standalone, "Evaluated on a benchmark dataset [1].")
    answer = ask("Which dataset does it use?", history=history)
    assert fake_answers.calls[0][0] == prompts.REWRITE_INSTRUCTION
    assert fake_answers.calls[1][0] == prompts.SYSTEM_INSTRUCTION
    assert search_spy == [standalone]
    assert answer.question == "Which dataset does it use?"
    assert answer.standalone_question == standalone
    assert answer.rewrite_applied is True
    assert answer.rewrite_fallback_reason is None
    assert answer.llm_calls == 2
    assert answer.timings["rewrite"] > 0
    assert answer.tokens == {"input": 200, "output": 80}
    assert fake_answers.calls[1][1].rstrip().endswith(f"Question: {standalone}")


def test_failed_rewrite_falls_back_to_the_original_question(answer_env, fake_answers, history, search_spy):
    from paperpilot.errors import LLMError

    fake_answers.add(LLMError("rate limited"), "Evaluated on a benchmark [1].")
    answer = ask("Which dataset does it use?", history=history)
    assert search_spy == ["Which dataset does it use?"]
    assert answer.standalone_question == "Which dataset does it use?"
    assert answer.rewrite_applied is False
    assert answer.rewrite_fallback_reason == "rewrite_failed"
    assert answer.text == "Evaluated on a benchmark [1]."
    assert answer.llm_calls == 2


def test_empty_rewrite_falls_back_to_the_original_question(answer_env, fake_answers, history, search_spy):
    fake_answers.add("   ", "Evaluated on a benchmark [1].")
    answer = ask("Which dataset does it use?", history=history)
    assert search_spy == ["Which dataset does it use?"]
    assert answer.rewrite_applied is False
    assert answer.rewrite_fallback_reason == "rewrite_empty"
