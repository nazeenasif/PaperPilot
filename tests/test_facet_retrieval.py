"""Section-aware facet retrieval (research R2): which sections each summary facet may search.
Fake embedder and a temporary library; no model and no network."""

import pytest

from paperpilot import library, prompts, service, store
from paperpilot.library import SearchResult
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


# --- step 2: Problem reads the Abstract and Introduction ---


def test_problem_sections_are_abstract_and_introduction():
    all_sections = ["Front Matter", "Abstract", "1 Introduction", "Methods", "Results", "Related Work"]
    assert prompts.facet_sections("problem", all_sections) == ["Abstract", "1 Introduction"]


def test_problem_falls_back_to_the_searchable_sections_when_neither_exists():
    assert prompts.facet_sections("problem", ["Front Matter", "Methods", "Results", "Related Work"]) == ["Methods", "Results"]


def test_other_facets_search_every_searchable_section():
    assert prompts.facet_sections("results", ["Front Matter", "Abstract", "Results"]) == ["Abstract", "Results"]


def test_problem_retrieves_only_from_the_abstract_and_introduction(paper_with_related_work):
    results = service.facet_results("problem", paper_with_related_work)
    assert {r.section for r in results} == {"Abstract", "Introduction"}


def test_problem_uses_the_whole_paper_when_it_has_no_abstract_or_introduction(tmp_path, make_pdf, library_env, fake_embedder, llm_env):
    paper = library.add_paper(make_pdf(tmp_path / "plain.pdf", references=False, title="A Study of Layout Recovery Methods",
                                       sections=[("1 Method", BODY), ("2 Results", BODY + " Results.")]))
    assert {r.section for r in service.facet_results("problem", paper.paper_id)} == {"Methods", "Results"}


# --- step 3: Limitations reads its own sections and the whole paper ---


def hit(passage_id, score, section="Results"):
    return SearchResult(1, score, passage_id, "paper", "A Paper", section, 1, passage_id)


@pytest.fixture
def scripted_search(monkeypatch):
    """Replace search: `named` answers a search of the Limitations sections, `whole` any other."""

    def install(sections, named, whole):
        calls = []

        def fake(query, k=None, paper_ids=None, sections=None):
            calls.append((query, k, paper_ids, sections))
            return named[:k] if sections == install.wanted else whole[:k]

        install.wanted = [s for s in sections if s in ("Limitations", "Discussion", "Conclusion")]
        monkeypatch.setattr(library, "paper_sections", lambda paper_id: sections)
        monkeypatch.setattr(library, "search", fake)
        return calls

    return install


def test_limitation_sections_are_found_by_name_among_the_searchable_ones():
    sections = ["Front Matter", "Abstract", "Limitations", "4 Discussion", "Conclusion and Future Work", "Related Work"]
    assert prompts.limitation_sections(sections) == ["Limitations", "4 Discussion", "Conclusion and Future Work"]
    assert prompts.limitation_sections(["Abstract", "Methods", "Results"]) == []


def test_limitations_takes_two_from_its_sections_and_two_from_the_whole_paper(scripted_search):
    sections = ["Abstract", "Results", "Discussion", "Conclusion", "Related Work"]
    calls = scripted_search(sections, [hit("d1", 0.60, "Discussion"), hit("c1", 0.55, "Conclusion"), hit("d2", 0.50, "Discussion")],
                            [hit("r1", 0.70), hit("r2", 0.65), hit("r3", 0.62), hit("r4", 0.61)])
    results = service.facet_results("limitations", "paper")
    assert sorted(r.passage_id for r in results) == ["c1", "d1", "r1", "r2"]
    query = prompts.FACETS["limitations"].query
    assert calls == [(query, 2, ["paper"], ["Discussion", "Conclusion"]),
                     (query, 4, ["paper"], ["Abstract", "Results", "Discussion", "Conclusion"])]


def test_limitations_replaces_a_passage_the_whole_paper_search_repeats(scripted_search):
    scripted_search(["Results", "Discussion"], [hit("d1", 0.70, "Discussion"), hit("d2", 0.65, "Discussion")],
                    [hit("d1", 0.70, "Discussion"), hit("d2", 0.65, "Discussion"), hit("r1", 0.60), hit("r2", 0.58)])
    assert sorted(r.passage_id for r in service.facet_results("limitations", "paper")) == ["d1", "d2", "r1", "r2"]


def test_limitations_passages_are_ranked_best_first(scripted_search):
    scripted_search(["Results", "Discussion"], [hit("d1", 0.55, "Discussion"), hit("d2", 0.50, "Discussion")],
                    [hit("r1", 0.70), hit("r2", 0.65)])
    results = service.facet_results("limitations", "paper")
    assert [r.passage_id for r in results] == ["r1", "r2", "d1", "d2"]
    assert [r.rank for r in results] == [1, 2, 3, 4]


def test_limitations_with_one_passage_in_its_sections_reads_three(scripted_search):
    scripted_search(["Results", "Conclusion"], [hit("c1", 0.55, "Conclusion")], [hit("r1", 0.70), hit("r2", 0.65), hit("r3", 0.60)])
    assert sorted(r.passage_id for r in service.facet_results("limitations", "paper")) == ["c1", "r1", "r2"]


def test_limitations_without_its_sections_reads_four_from_the_whole_paper(scripted_search):
    calls = scripted_search(["Abstract", "Results", "Related Work"], [],
                            [hit("r1", 0.70), hit("r2", 0.65), hit("r3", 0.62), hit("r4", 0.61)])
    assert len(service.facet_results("limitations", "paper")) == 4
    assert [(k, sections) for _, k, _, sections in calls] == [(4, ["Abstract", "Results"])]


def test_limitations_retrieves_from_a_stored_paper_without_related_work(tmp_path, make_pdf, library_env, fake_embedder, llm_env):
    paper = library.add_paper(make_pdf(tmp_path / "limits.pdf", references=False, title="A Study of Layout Recovery Methods", sections=[
        ("Abstract", BODY), ("1 Introduction", BODY + " Introduction."), ("2 Related Work", RELATED),
        ("3 Method", BODY + " Method."), ("4 Results", BODY + " Results."), ("5 Discussion", BODY + " Discussion."),
        ("6 Conclusion", BODY + " Conclusion."),
    ]))
    results = service.facet_results("limitations", paper.paper_id)
    sections = [r.section for r in results]
    assert len(results) == 4 and len({r.passage_id for r in results}) == 4
    assert "Related Work" not in sections and {"Discussion", "Conclusion"} <= set(sections)
