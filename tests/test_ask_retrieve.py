"""`service.ask(..., retrieve=...)` (Feature 5, contracts/engine-api.md): the evaluation harness
runs reranking and hybrid search through the real answer pipeline. With no `retrieve`, `ask` is
unchanged. Scripted LLM and fake embedder only."""

from dataclasses import replace

from paperpilot import library, prompts, service
from paperpilot.service import Retrieval, ask

QUESTION = "Which evaluation dataset was used?"


def test_without_retrieve_ask_searches_the_library_as_before(answer_env, fake_answers, monkeypatch):
    calls = []
    real = library.search

    def spy(query, k=None, paper_ids=None, sections=None):
        calls.append((query, k, paper_ids, sections))
        return real(query, k=k, paper_ids=paper_ids, sections=sections)

    monkeypatch.setattr(library, "search", spy)
    fake_answers.add("Evaluated on a benchmark dataset [1].")
    answer = ask(QUESTION, paper_ids=[answer_env.paper_id], k=3)
    assert calls == [(QUESTION, 3, [answer_env.paper_id], None)]
    assert answer.citations.valid == [1]


def test_a_custom_retrieve_supplies_the_passages(answer_env, fake_answers):
    real = library.search(QUESTION, k=6)
    chosen = list(reversed(real))[:2]
    seen = []

    def retrieve(question, k, paper_ids):
        seen.append((question, k, paper_ids))
        return Retrieval(chosen, gate_score=0.99)

    fake_answers.add("From the chosen passages [2].")
    answer = ask(QUESTION, k=4, retrieve=retrieve)
    assert seen == [(QUESTION, 4, None)]
    assert [p.passage_id for p in answer.passages] == [r.passage_id for r in chosen]
    assert prompts.build_answer_prompt(QUESTION, answer.passages) in fake_answers.calls[0][1]


def test_the_gate_uses_the_gate_score_not_the_passages_scores(answer_env, fake_answers, monkeypatch):
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "0.5")
    low = [replace(r, score=0.1) for r in library.search(QUESTION, k=3)]
    fake_answers.add("Answered from low-scored passages [1].")
    answer = ask(QUESTION, retrieve=lambda q, k, ids: Retrieval(low, gate_score=0.9))
    assert answer.not_found is False and len(fake_answers.calls) == 1


def test_a_gate_score_under_the_threshold_is_not_found_with_no_request(answer_env, fake_answers, monkeypatch):
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "0.5")
    high = [replace(r, score=0.95) for r in library.search(QUESTION, k=3)]
    answer = ask(QUESTION, retrieve=lambda q, k, ids: Retrieval(high, gate_score=0.2))
    assert (answer.not_found, answer.fallback_reason) == (True, "below_threshold")
    assert fake_answers.calls == []


def test_nothing_retrieved_is_not_found_with_no_request(answer_env, fake_answers):
    answer = ask(QUESTION, retrieve=lambda q, k, ids: Retrieval([], gate_score=None))
    assert (answer.not_found, answer.fallback_reason) == (True, "no_passages")
    assert fake_answers.calls == []


def test_a_follow_up_retrieves_with_the_standalone_question(answer_env, fake_answers):
    seen = []

    def retrieve(question, k, paper_ids):
        seen.append(question)
        return Retrieval(library.search(question, k=k), gate_score=0.99)

    fake_answers.add("Which dataset did the system use?", "A benchmark dataset [1].")
    ask("And which one?", history=[service.Turn("user", "Tell me about the system."),
                                   service.Turn("assistant", "It answers questions [1].")], retrieve=retrieve)
    assert seen == ["Which dataset did the system use?"]
