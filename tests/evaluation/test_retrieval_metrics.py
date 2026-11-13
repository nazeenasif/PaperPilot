"""Retrieval metrics (spec FR-006, FR-007; research R3): evidence rank, hit@k, MRR, gating and
search scope. Pure data plus a fixture library with the fake embedder; no model, no network."""

from dataclasses import replace

import pytest

from evaluation import retrieval
from paperpilot.library import SearchResult

A, B = "aaaaaaaaaaaa", "bbbbbbbbbbbb"
ARXIV_OF = {A: "1111.11111", B: "2222.22222"}


def hit(paper_id, text, score=0.5, rank=1):
    return SearchResult(rank=rank, score=score, passage_id=f"{paper_id}-{rank}", paper_id=paper_id,
                        title="T", section="S", page=1, text=text)


def ranked(*items):
    return [replace(h, rank=n) for n, h in enumerate(items, start=1)]


def single(**overrides):
    q = {"id": "s1", "kind": "single", "question": "Q?", "scope": "library", "papers": ["1111.11111"],
         "evidence": [{"paper": "1111.11111", "page": 1, "phrase": "the answer is here"}]}
    return {**q, **overrides}


# --- rank ---


def test_the_rank_is_the_first_relevant_passage():
    passages = ranked(hit(A, "nothing"), hit(A, "The answer is HERE, said the paper."), hit(A, "the answer is here"))
    assert retrieval.evidence_rank(single(), passages, ARXIV_OF) == 2


def test_a_passage_from_another_paper_is_not_relevant():
    passages = ranked(hit(B, "the answer is here"), hit(A, "the answer is here"))
    assert retrieval.evidence_rank(single(), passages, ARXIV_OF) == 2


def test_evidence_matching_tolerates_ligatures_and_hyphens():
    q = single(evidence=[{"paper": "1111.11111", "page": 1, "phrase": "fine-tuning stage"}])
    assert retrieval.evidence_rank(q, ranked(hit(A, "the ﬁne-\ntuning stage")), ARXIV_OF) == 1


def test_no_relevant_passage_within_the_shortlist_gives_none():
    passages = ranked(*[hit(A, "nothing") for _ in range(20)], hit(A, "the answer is here"))
    assert retrieval.evidence_rank(single(), passages, ARXIV_OF) is None


def test_a_cross_paper_rank_is_where_every_paper_is_covered():
    q = single(kind="cross", papers=["1111.11111", "2222.22222"],
               evidence=[{"paper": "1111.11111", "page": 1, "phrase": "alpha fact"},
                         {"paper": "2222.22222", "page": 2, "phrase": "beta fact"}])
    passages = ranked(hit(A, "alpha fact"), hit(A, "noise"), hit(B, "beta fact"))
    assert retrieval.evidence_rank(q, passages, ARXIV_OF) == 3
    assert retrieval.evidence_rank(q, ranked(hit(A, "alpha fact"), hit(A, "noise")), ARXIV_OF) is None


# --- metrics ---


def row(qid, kind, rank=None, gate=None, gated=None):
    return {"id": qid, "kind": kind, "rank": rank, "gate_score": gate, "gated": gated}


def test_hit_at_k_and_mrr():
    rows = [row("a", "single", 1), row("b", "single", 4), row("c", "single", None), row("d", "single", 8)]
    m = retrieval.metrics(rows)
    assert m["hit@1"] == 0.25 and m["hit@3"] == 0.25 and m["hit@6"] == 0.5 and m["hit@10"] == 0.75
    assert m["mrr"] == pytest.approx((1 + 0.25 + 0 + 0.125) / 4, abs=0.001)
    assert m["answerable"] == 4


def test_metrics_per_kind_and_gated_not_founds():
    rows = [row("a", "single", 1), row("b", "cross", None),
            row("n1", "near_miss", gate=0.4, gated=True), row("n2", "near_miss", gate=0.7, gated=False),
            row("o1", "off_topic", gate=0.2, gated=True)]
    m = retrieval.metrics(rows)
    assert m["per_kind"]["single"]["hit@6"] == 1.0 and m["per_kind"]["cross"]["mrr"] == 0.0
    assert m["per_kind"]["near_miss"] == {"questions": 2, "gated": 1}
    assert m["gated_not_found"] == {"gated": 2, "of": 3}
    assert m["hit@6"] == 0.5  # not-found kinds are not answerable


def test_metrics_with_no_answerable_questions_are_none():
    assert retrieval.metrics([row("n", "near_miss", gate=0.1, gated=True)])["hit@6"] is None


# --- question text and scope ---


def test_a_follow_up_is_searched_by_its_standalone_wording():
    q = single(kind="follow_up", question="And that one?", standalone="How does LoRA work?")
    assert retrieval.query_text(q) == "How does LoRA work?"
    assert retrieval.query_text(single()) == "Q?"


def test_searches_cover_the_golden_papers_or_the_one_paper():
    ids = {"1111.11111": A, "2222.22222": B}
    assert retrieval.scope_paper_ids(single(), ids) == [A, B]
    assert retrieval.scope_paper_ids(single(scope="paper"), ids) == [A]


# --- the vector retriever on a real (temporary) library ---


def test_the_vector_retriever_returns_the_shortlist_and_gates_on_its_top_score(eval_paper):
    got = retrieval.vector_retrieve("large corpus of abstracts", [eval_paper.paper_id])
    assert 1 <= len(got.passages) <= retrieval.SHORTLIST
    assert [p.rank for p in got.passages] == list(range(1, len(got.passages) + 1))
    assert got.gate_score == max(p.score for p in got.passages)
    assert all(p.paper_id == eval_paper.paper_id for p in got.passages)


def test_evaluate_scores_a_golden_set(eval_paper, tmp_path):
    EVAL_ARXIV = "2401.00001"  # the eval_paper fixture's arXiv ID
    from evaluation import golden

    questions = [single(papers=[EVAL_ARXIV], evidence=[{"paper": EVAL_ARXIV, "page": 1,
                                                        "phrase": "large corpus of abstracts"}],
                        question="Which corpus is used for pre-training?"),
                 {"id": "n1", "kind": "near_miss", "question": "What is the capital of Peru?", "scope": "library",
                  "papers": [EVAL_ARXIV], "expected": "not_found", "evidence": []}]
    path = tmp_path / "golden.json"
    import json
    path.write_text(json.dumps({"version": 1, "papers": [EVAL_ARXIV], "questions": questions}), encoding="utf-8")
    out = retrieval.evaluate(golden.load_golden(path), retrieval.vector_retrieve, threshold=0.99)
    by_id = {r["id"]: r for r in out["questions"]}
    assert by_id["s1"]["rank"] is not None and by_id["n1"]["gated"] is True
    assert out["metrics"]["gated_not_found"] == {"gated": 1, "of": 1}
