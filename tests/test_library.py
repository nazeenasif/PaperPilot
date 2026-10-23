"""Tests for the public library API (contracts/library-api.md), run offline.

Uses the conftest fixtures: a temporary library, the fake embedder, and generated PDFs.
"""

import pytest

from paperpilot import store
from paperpilot.errors import EmptyQueryError, NoTextError, PdfReadError, StorageError
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
