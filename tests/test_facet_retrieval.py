"""Section-aware facet retrieval (research R2): which sections each summary facet may search.
Fake embedder and a temporary library; no model and no network."""

import pytest

from paperpilot import library, prompts, service, store
from paperpilot.store import build_where

RELATED = (
    "Earlier systems proposed the method and model architecture in other ways. Smith and colleagues "
    "describe how their proposed method works, and Jones reports the limitations, weaknesses and "
    "failure cases of that model architecture, along with main results, datasets and benchmarks used, "
    "the problem, the motivation and the research question addressed by those other papers."
)
BODY = (
    "We train a small network on a private collection of scanned documents and measure how often it "
    "recovers the original layout. Pages are split into blocks, each block is labelled by hand, and "
    "the labels are compared with the predictions after every epoch of training on the collection."
)


@pytest.fixture
def paper_with_related_work(tmp_path, make_pdf, library_env, fake_embedder, llm_env, monkeypatch):
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "0.0")
    path = make_pdf(tmp_path / "related.pdf", references=False, sections=[
        ("Abstract", BODY), ("1 Introduction", BODY + " Introduction."), ("2 Related Work", RELATED),
        ("3 Method", BODY + " Method."),
    ], title="A Study of Scanned Document Layout Recovery")
    return library.add_paper(path).paper_id


# --- which sections may be searched ---


@pytest.mark.parametrize("excluded", ["Related Work", "Related Works", "RELATED WORK", "Front Matter"])
def test_related_work_and_front_matter_are_not_searchable(excluded):
    assert prompts.searchable_sections([excluded, "Methods", "Results"]) == ["Methods", "Results"]


def test_a_section_merely_containing_a_similar_word_stays_searchable():
    assert prompts.searchable_sections(["Work Plan", "Related Tasks"]) == ["Work Plan", "Related Tasks"]


def test_a_paper_with_only_excluded_sections_searches_them_all():
    """A paper with no detected headings is all Front Matter; better searched than left empty."""
    assert prompts.searchable_sections(["Front Matter"]) == ["Front Matter"]
    assert prompts.searchable_sections(["Front Matter", "Related Work"]) == ["Front Matter", "Related Work"]


# --- filters ---


def test_build_where_combines_papers_and_sections():
    assert build_where(["a"], ["x", "y"]) == {"$and": [{"paper_id": {"$in": ["a"]}}, {"section": {"$in": ["x", "y"]}}]}
    assert build_where(None, ["x"]) == {"section": {"$in": ["x"]}}
    assert build_where(["a"], None) == {"paper_id": {"$in": ["a"]}}
    assert build_where(None, None) is None


def test_search_can_be_limited_to_sections(paper_with_related_work):
    results = library.search(RELATED, k=4, paper_ids=[paper_with_related_work], sections=["Methods"])
    assert {r.section for r in results} == {"Methods"}


def test_search_without_sections_is_unchanged(paper_with_related_work):
    results = library.search(RELATED, k=1, paper_ids=[paper_with_related_work])
    assert store.paper_metadata(paper_with_related_work) and results[0].section == "Related Work"


def test_paper_sections_lists_each_section_once(paper_with_related_work):
    assert sorted(library.paper_sections(paper_with_related_work)) == ["Abstract", "Introduction", "Methods", "Related Work"]


# --- facets ---


@pytest.mark.parametrize("facet", list(prompts.FACETS))
def test_no_facet_retrieves_related_work_even_when_it_matches_best(paper_with_related_work, facet):
    sections = {r.section for r in service.facet_results(facet, paper_with_related_work)}
    assert sections and "Related Work" not in sections


def test_a_summary_cites_no_related_work_passage(paper_with_related_work, monkeypatch):
    from paperpilot import llm
    from test_summarize import PromptReadingLLM

    monkeypatch.setattr(llm, "generate", PromptReadingLLM())
    summary = service.summarize(paper_with_related_work)
    assert summary.passages and "Related Work" not in {p.section for p in summary.passages}


def test_a_paper_that_is_all_related_work_still_gets_passages(tmp_path, make_pdf, library_env, fake_embedder, llm_env):
    paper = library.add_paper(make_pdf(tmp_path / "survey.pdf", references=False, sections=[("Related Work", RELATED)],
                                       title="A Survey of Layout Recovery Methods"))
    assert service.facet_results("method", paper.paper_id)
