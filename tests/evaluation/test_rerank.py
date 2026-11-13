"""Cross-encoder reranking of the vector top 20 (research R4), with a fake cross-encoder: no
download, no torch, no network."""

import json

import pytest

from evaluation import golden, retrieval
from evaluation.experiments import Experiment
from paperpilot.library import SearchResult

MINILM = {"method": "rerank", "shortlist": 20, "reranker": "cross-encoder/ms-marco-MiniLM-L6-v2",
          "revision": "233902d25c44"}


def passage(n, text, score):
    return SearchResult(rank=n, score=score, passage_id=f"p-{n}", paper_id="p", title="T", section="S",
                        page=1, text=text)


class FakeCrossEncoder:
    """Scores a pair by how often the word 'gold' appears in the passage."""

    def __init__(self):
        self.calls = []

    def predict(self, pairs, batch_size=8, show_progress_bar=False):
        self.calls.append(list(pairs))
        return [text.count("gold") for _, text in pairs]


@pytest.fixture
def vector(monkeypatch):
    shortlist = [passage(1, "plain", 0.9), passage(2, "gold gold", 0.8), passage(3, "gold", 0.7)]

    def fake_vector(text, paper_ids):
        fake_vector.calls += 1
        return retrieval.Ranked(shortlist, 0.9)

    fake_vector.calls = 0
    monkeypatch.setattr(retrieval, "vector_retrieve", fake_vector)
    return fake_vector


def test_reranking_reorders_the_vector_shortlist(vector):
    model = FakeCrossEncoder()
    got = retrieval.rerank_retriever(model)("question", ["p"])
    assert [p.passage_id for p in got.passages] == ["p-2", "p-3", "p-1"]
    assert [p.rank for p in got.passages] == [1, 2, 3]
    assert model.calls == [[("question", "plain"), ("question", "gold gold"), ("question", "gold")]]


def test_the_gate_stays_the_top_vector_score(vector):
    assert retrieval.rerank_retriever(FakeCrossEncoder())("question", ["p"]).gate_score == 0.9


def test_the_model_is_loaded_at_its_pinned_revision(monkeypatch):
    loaded = []
    monkeypatch.setattr(retrieval, "load_cross_encoder", lambda name, revision: loaded.append((name, revision)) or FakeCrossEncoder())
    retrieval.retriever_for(Experiment("rerank-minilm-l6", changes={"retrieval": MINILM}))
    assert loaded == [("cross-encoder/ms-marco-MiniLM-L6-v2", "233902d25c44")]


def _golden(tmp_path):
    arxiv = "2401.00001"
    path = tmp_path / "golden.json"
    path.write_text(json.dumps({"version": 1, "papers": [arxiv], "questions": [
        {"id": "s1", "kind": "single", "question": "Which corpus?", "scope": "library", "papers": [arxiv],
         "expected": "Abstracts.", "evidence": [{"paper": arxiv, "page": 1, "phrase": "large corpus of abstracts"}]}]}),
        encoding="utf-8")
    return golden.load_golden(path)


def test_a_load_failure_stops_the_experiment_before_any_question(eval_paper, tmp_path, monkeypatch, vector):
    def broken(name, revision):
        raise OSError("revision not found")

    monkeypatch.setattr(retrieval, "load_cross_encoder", broken)
    loaded = _golden(tmp_path)
    baseline = retrieval.baseline_configuration(loaded)
    with pytest.raises(ValueError, match="revision not found"):
        retrieval.run_experiment(Experiment("rerank-minilm-l6", changes={"retrieval": MINILM}), loaded, baseline)
    assert vector.calls == 0


def test_the_configuration_records_the_reranker_and_revision(eval_paper, tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval, "load_cross_encoder", lambda name, revision: FakeCrossEncoder())
    loaded = _golden(tmp_path)
    result = retrieval.run_experiment(Experiment("rerank-minilm-l6", changes={"retrieval": MINILM}), loaded,
                                      retrieval.baseline_configuration(loaded))
    assert result["configuration"]["retrieval"]["reranker"] == "cross-encoder/ms-marco-MiniLM-L6-v2"
    assert result["configuration"]["retrieval"]["revision"] == "233902d25c44"
    assert result["retrieval"]["answerable"] == 1
