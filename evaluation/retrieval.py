"""Retrieval evaluation: evidence ranks, hit@k, MRR and gated not-founds, with no model requests
(spec FR-006-FR-008; research R3-R6).

A retriever turns a question's text and the papers in scope into a shortlist of up to SHORTLIST
passages, best first, and the score its relevance gate compares with the threshold. Every
retriever gates on the top vector score, so RELEVANCE_THRESHOLD keeps its meaning (research R4).
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from evaluation import golden as golden_module
from paperpilot import library
from paperpilot.config import load_settings

SHORTLIST = 20
KS = (1, 3, 6, 10)


@dataclass(frozen=True)
class Ranked:
    """A retriever's shortlist, best first and ranked from 1, and its gate score."""

    passages: list[library.SearchResult]
    gate_score: float | None


Retriever = Callable[[str, list[str]], Ranked]


def query_text(q: dict) -> str:
    """What is searched: a follow-up's standalone wording, otherwise the question (FR-003)."""
    if q.get("kind") == "follow_up" and str(q.get("standalone", "")).strip():
        return q["standalone"]
    return q["question"]


def scope_paper_ids(q: dict, paper_ids: dict[str, str]) -> list[str]:
    """The papers searched: the question's one paper for `scope: paper`, else every golden paper
    (`paper_ids` maps arXiv ID to paper ID, in golden-set order)."""
    if q.get("scope") == "paper":
        return [paper_ids[q["papers"][0]]]
    return list(paper_ids.values())


def evidence_rank(q: dict, passages: list[library.SearchResult], arxiv_of: dict[str, str],
                  limit: int = SHORTLIST) -> int | None:
    """The position by which every required paper has a relevant passage: one of that paper's that
    contains one of its evidence phrases (FR-007). None when that is not reached within `limit`."""
    phrases: dict[str, list[str]] = {}
    for ev in q.get("evidence", []):
        phrases.setdefault(ev["paper"], []).append(golden_module.normalise(ev["phrase"]))
    needed = set(q.get("papers", []))
    if not needed or not phrases:
        return None
    covered: set[str] = set()
    for position, passage in enumerate(passages[:limit], start=1):
        arxiv = arxiv_of.get(passage.paper_id)
        if arxiv in needed and arxiv not in covered:
            text = golden_module.normalise(passage.text)
            if any(phrase in text for phrase in phrases.get(arxiv, [])):
                covered.add(arxiv)
                if covered == needed:
                    return position
    return None


def _ranking(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {f"hit@{k}": None for k in KS} | {"mrr": None, "answerable": 0}
    figures = {f"hit@{k}": round(sum(r["rank"] is not None and r["rank"] <= k for r in rows) / n, 3) for k in KS}
    figures["mrr"] = round(sum(1 / r["rank"] for r in rows if r["rank"]) / n, 3)
    figures["answerable"] = n
    return figures


def metrics(rows: list[dict]) -> dict:
    """hit@k and MRR over answerable questions, the same per kind, and gated not-founds."""
    answerable = [r for r in rows if r["kind"] in golden_module.ANSWERABLE]
    refusals = [r for r in rows if r["kind"] in golden_module.NOT_FOUND_KINDS]
    result = _ranking(answerable)
    per_kind: dict[str, dict] = {}
    for kind in dict.fromkeys(r["kind"] for r in rows):
        of_kind = [r for r in rows if r["kind"] == kind]
        if kind in golden_module.ANSWERABLE:
            per_kind[kind] = _ranking(of_kind)
        else:
            per_kind[kind] = {"questions": len(of_kind), "gated": sum(bool(r["gated"]) for r in of_kind)}
    result["per_kind"] = per_kind
    result["gated_not_found"] = {"gated": sum(bool(r["gated"]) for r in refusals), "of": len(refusals)}
    return result


def vector_retrieve(text: str, paper_ids: list[str]) -> Ranked:
    """Today's search: the vector top SHORTLIST, gated on its top score."""
    results = library.search(text, k=SHORTLIST, paper_ids=paper_ids)
    return Ranked(results, max((r.score for r in results), default=None))


def golden_papers(golden: golden_module.GoldenSet) -> dict[str, str]:
    """arXiv ID to paper ID for the golden papers in the active library; raises ValueError for a missing one."""
    by_arxiv = {p.arxiv_id: p.paper_id for p in library.list_papers() if p.arxiv_id}
    missing = [a for a in golden.papers if a not in by_arxiv]
    if missing:
        raise ValueError(f"Not in the library: {', '.join(missing)}")
    return {arxiv: by_arxiv[arxiv] for arxiv in golden.papers}


def evaluate(golden: golden_module.GoldenSet, retrieve: Retriever, threshold: float | None = None) -> dict:
    """Run every golden question through `retrieve`; return per-question rows (no passage text),
    the metrics and the mean seconds per question."""
    threshold = load_settings().relevance_threshold if threshold is None else threshold
    paper_ids = golden_papers(golden)
    arxiv_of = {pid: arxiv for arxiv, pid in paper_ids.items()}
    rows, seconds = [], 0.0
    for q in golden.questions:
        start = time.perf_counter()
        got = retrieve(query_text(q), scope_paper_ids(q, paper_ids))
        seconds += time.perf_counter() - start
        gate = got.gate_score
        rows.append({
            "id": q["id"], "kind": q["kind"],
            "rank": evidence_rank(q, got.passages, arxiv_of) if q["kind"] in golden_module.ANSWERABLE else None,
            "gate_score": gate,
            "gated": gate is None or gate < threshold,
        })
    return {"questions": rows, "metrics": metrics(rows),
            "latency_s": round(seconds / len(rows), 3) if rows else None}
