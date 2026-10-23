"""Tests for the public library API (contracts/library-api.md), run offline.

Uses the conftest fixtures: a temporary library, the fake embedder, and generated PDFs.
"""

import pytest

from paperpilot import ingest, store
from paperpilot.errors import EmptyQueryError, NoTextError, PdfReadError, StorageError, UnknownPaperError
from paperpilot.ingest import paper_id_for
from paperpilot.library import add_paper, search


@pytest.fixture
def paper(tmp_path, make_pdf, library_env, fake_embedder):
    """A generated test paper (not yet added) in an empty temporary library."""
    return make_pdf(tmp_path / "paper.pdf")


def test_add_paper_returns_result(paper):
    result = add_paper(paper)
    assert result.paper_id == paper_id_for(paper.read_bytes())
    assert result.title == "A Study of Searching Research Papers by Meaning"
    assert result.passage_count > 0
    assert result.already_present is False
    assert set(result.timings) >= {"parse", "embed", "store"}


def test_search_results_shape(paper):
    add_paper(paper)
    results = search("which evaluation dataset was used", k=3)
    assert 0 < len(results) <= 3
    assert [r.rank for r in results] == list(range(1, len(results) + 1))
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
    for r in results:
        assert 0.0 <= r.score <= 1.0
        assert r.paper_id == paper_id_for(paper.read_bytes())
        assert r.title == "A Study of Searching Research Papers by Meaning"
        assert r.section
        assert r.page >= 1
        assert r.text
        assert r.passage_id.startswith(r.paper_id + "-")


def test_search_uses_default_k(paper, monkeypatch):
    monkeypatch.setenv("TOP_K", "2")
    add_paper(paper)
    assert len(search("research papers")) == 2


def test_k_larger_than_library_returns_all_passages(paper):
    result = add_paper(paper)
    assert len(search("research papers", k=100)) == result.passage_count


def test_reference_text_is_never_stored(paper):
    add_paper(paper)
    results = search("refonlytoken referenced paper about citations", k=100)
    assert results
    assert all("refonlytoken" not in r.text for r in results)


def test_blank_pdf_raises_no_text_and_stores_nothing(tmp_path, make_pdf, library_env, fake_embedder):
    blank = make_pdf(tmp_path / "scan.pdf", blank=True)
    with pytest.raises(NoTextError):
        add_paper(blank)
    assert not store.has_paper(paper_id_for(blank.read_bytes()))
    assert search("anything") == []


def test_non_pdf_file_raises_pdf_read_error(tmp_path, library_env, fake_embedder):
    fake = tmp_path / "notes.pdf"
    fake.write_text("this is not a pdf")
    with pytest.raises(PdfReadError):
        add_paper(fake)


def test_missing_file_raises_pdf_read_error(tmp_path, library_env, fake_embedder):
    with pytest.raises(PdfReadError):
        add_paper(tmp_path / "missing.pdf")


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_empty_query_rejected(paper, query):
    add_paper(paper)
    with pytest.raises(EmptyQueryError):
        search(query)


def test_search_on_empty_library_returns_nothing(library_env, fake_embedder):
    assert search("what dataset was used for evaluation?") == []


def test_failed_write_is_cleaned_up_and_retry_succeeds(paper, monkeypatch):
    original_upsert = store.upsert_passages

    def write_then_fail(*args, **kwargs):
        original_upsert(*args, **kwargs)  # data reaches the store, then the write "fails"
        raise RuntimeError("disk full")

    monkeypatch.setattr(store, "upsert_passages", write_then_fail)
    with pytest.raises(StorageError):
        add_paper(paper)
    paper_id = paper_id_for(paper.read_bytes())
    assert not store.has_paper(paper_id)
    assert search("research papers") == []

    monkeypatch.setattr(store, "upsert_passages", original_upsert)
    result = add_paper(paper)
    assert result.already_present is False
    assert result.passage_count > 0
    assert store.has_paper(paper_id)


# --- US2: adding the same paper twice never duplicates data ---


def test_adding_same_file_twice_stores_nothing_new(paper):
    first = add_paper(paper)
    count = store.get_collection().count()
    second = add_paper(paper)
    assert second.already_present is True
    assert second.paper_id == first.paper_id
    assert second.title == first.title
    assert second.passage_count == first.passage_count
    assert store.get_collection().count() == count


def test_renamed_copy_is_recognised_as_same_paper(paper, tmp_path):
    first = add_paper(paper)
    copy = tmp_path / "renamed-copy.pdf"
    copy.write_bytes(paper.read_bytes())
    second = add_paper(copy)
    assert second.already_present is True
    assert second.paper_id == first.paper_id


def test_re_add_skips_parsing_and_embedding(paper, monkeypatch):
    add_paper(paper)

    def fail(*args, **kwargs):
        raise AssertionError("should not be called for a paper already in the library")

    monkeypatch.setattr(ingest, "parse_pdf", fail)
    monkeypatch.setattr(store, "embed_passages", fail)
    assert add_paper(paper).already_present is True


# --- US3: the library persists across restarts ---


def test_library_survives_reopening_from_disk(paper, library_env):
    result = add_paper(paper)
    before = [r.passage_id for r in search("which evaluation dataset was used", k=4)]
    old_collection = store.get_collection()

    store.reset_cache()  # simulate a restart: a new client on the same folder

    assert store.get_collection() is not old_collection
    assert (library_env / "chroma.sqlite3").is_file()
    assert store.has_paper(result.paper_id)
    after = [r.passage_id for r in search("which evaluation dataset was used", k=4)]
    assert after == before
    assert add_paper(paper).already_present is True


# --- US4: search within selected papers ---


@pytest.fixture
def three_papers(tmp_path, make_pdf, library_env, fake_embedder):
    """Three different papers added to an empty temporary library; returns their IDs."""
    titles = ["A Study of Searching Research Papers by Meaning", "Second Paper on Search", "Third Paper on Search"]
    return [add_paper(make_pdf(tmp_path / f"p{i}.pdf", title=t)).paper_id for i, t in enumerate(titles)]


def test_filter_to_one_paper(three_papers):
    target = three_papers[1]
    results = search("research papers search", k=20, paper_ids=[target])
    assert results
    assert {r.paper_id for r in results} == {target}


def test_filter_to_two_papers(three_papers):
    targets = three_papers[:2]
    results = search("research papers search", k=20, paper_ids=targets)
    assert results
    assert {r.paper_id for r in results} <= set(targets)


def test_empty_filter_searches_whole_library(three_papers):
    everything = [r.passage_id for r in search("research papers search", k=20)]
    assert [r.passage_id for r in search("research papers search", k=20, paper_ids=[])] == everything
    assert len({pid.rsplit("-", 1)[0] for pid in everything}) == 3


def test_unknown_paper_in_filter_raises(three_papers):
    with pytest.raises(UnknownPaperError) as error:
        search("research papers", paper_ids=[three_papers[0], "000000000000"])
    assert "000000000000" in str(error.value)
