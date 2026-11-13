"""Hybrid search: BM25 fused with the vector list by reciprocal rank fusion (research R5).
A fixture library with the fake embedder; no model, no network."""

import json
from importlib import metadata

import pytest

from evaluation import golden, retrieval
from evaluation.experiments import Experiment

HYBRID = {"method": "hybrid", "shortlist": 20, "rrf_k": 60, "bm25": {"k1": 1.5, "b": 0.75}}


@pytest.mark.parametrize(("text", "tokens"), [
    ("GPT-3 beats SST-2 in v1.1.", ["gpt-3", "beats", "sst-2", "in", "v1.1"]),
    ("ﬁne Tuning", ["fine", "tuning"]),
    ("BERT, RoBERTa; end.", ["bert", "roberta", "end"]),
])
def test_tokens(text, tokens):
    assert retrieval.tokenize(text) == tokens


def test_rrf_with_k_60_orders_two_lists():
    assert retrieval.rrf_fuse([["a", "b", "c"], ["c", "a", "d"]], k=60) == ["a", "c", "b", "d"]


def test_rrf_ties_go_to_the_better_best_rank_then_the_vector_order():
    assert retrieval.rrf_fuse([["x", "y"], ["y", "x"]], k=60) == ["x", "y"]
    assert retrieval.rrf_fuse([["p", "q", "r"], ["r", "s", "p"]], k=60)[:2] == ["p", "r"]


def test_bm25_runs_over_exactly_the_scoped_passages(eval_paper, monkeypatch):
    from paperpilot import store

    built = []
    real = retrieval.BM25Okapi

    def spy(corpus, k1, b):
        built.append((len(corpus), k1, b))
        return real(corpus, k1=k1, b=b)

    monkeypatch.setattr(retrieval, "BM25Okapi", spy)
    retrieval.hybrid_retriever(rrf_k=60, k1=1.5, b=0.75)("large corpus of abstracts", [eval_paper.paper_id])
    stored = len(store.paper_passages(eval_paper.paper_id))
    assert built == [(stored, 1.5, 0.75)]


def test_hybrid_returns_a_ranked_shortlist_gated_on_the_vector_score(eval_paper):
    paper = [eval_paper.paper_id]
    got = retrieval.hybrid_retriever(rrf_k=60, k1=1.5, b=0.75)("Ours 91.7 accuracy", paper)
    assert got.gate_score == retrieval.vector_retrieve("Ours 91.7 accuracy", paper).gate_score
    assert [p.rank for p in got.passages] == list(range(1, len(got.passages) + 1))
    assert len(got.passages) <= retrieval.SHORTLIST
    assert len({p.passage_id for p in got.passages}) == len(got.passages)


def test_a_keyword_match_rises_above_the_vector_order(eval_paper, monkeypatch):
    """A passage BM25 ranks first is in the fused list even if the vector list put it last."""
    paper = [eval_paper.paper_id]
    got = retrieval.hybrid_retriever(rrf_k=60, k1=1.5, b=0.75)("91.7", paper)
    assert "91.7" in got.passages[0].text or "91.7" in got.passages[1].text


def test_the_configuration_records_the_fusion_and_the_library_version(eval_paper, tmp_path):
    arxiv = "2401.00001"
    path = tmp_path / "golden.json"
    path.write_text(json.dumps({"version": 1, "papers": [arxiv], "questions": [
        {"id": "s1", "kind": "single", "question": "Which corpus?", "scope": "library", "papers": [arxiv],
         "expected": "Abstracts.", "evidence": [{"paper": arxiv, "page": 1, "phrase": "large corpus of abstracts"}]}]}),
        encoding="utf-8")
    loaded = golden.load_golden(path)
    result = retrieval.run_experiment(Experiment("hybrid-rrf60", changes={"retrieval": HYBRID}), loaded,
                                      retrieval.baseline_configuration(loaded))
    recorded = result["configuration"]["retrieval"]
    assert recorded["rrf_k"] == 60 and recorded["bm25"] == {"k1": 1.5, "b": 0.75}
    assert recorded["rank_bm25"] == metadata.version("rank-bm25")
