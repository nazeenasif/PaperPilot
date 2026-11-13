"""Stored PDFs, attach-time highlight mapping, passage views and re-processing
(spec FR-013–FR-015, FR-018, FR-018a; research R4, R14; ADR-0006)."""

import json

import pytest

from paperpilot import ingest, library, store
from paperpilot.errors import PdfMissingError, UnknownPaperError, UnknownPassageError


def pdf_dir(library_dir):
    return library_dir / "pdfs"


@pytest.fixture
def spies(monkeypatch):
    """Count calls to ingest.parse_pdf and store.embed_passages (after the fake embedder)."""
    calls = {"parse": 0, "embed": 0}
    real_parse, real_embed = ingest.parse_pdf, store.embed_passages

    def parse(*args, **kwargs):
        calls["parse"] += 1
        return real_parse(*args, **kwargs)

    def embed(*args, **kwargs):
        calls["embed"] += 1
        return real_embed(*args, **kwargs)

    monkeypatch.setattr(ingest, "parse_pdf", parse)
    monkeypatch.setattr(store, "embed_passages", embed)
    return calls


@pytest.fixture
def paper_file(tmp_path, make_pdf):
    return make_pdf(tmp_path / "paper.pdf")


def change_chunking(monkeypatch):
    """Smaller passages than the stored ones (the generated paragraphs are ~60 words)."""
    monkeypatch.setenv("CHUNK_WORDS", "30")
    monkeypatch.setenv("CHUNK_OVERLAP", "5")
    monkeypatch.setenv("MIN_CHUNK_WORDS", "5")


def forget_pdf(library_dir, paper_id):
    """Simulate a paper added before Feature 3: passages stored, no PDF copy or layout."""
    for path in pdf_dir(library_dir).glob(f"{paper_id}*"):
        path.unlink()


# --- adding a new paper ---


def test_add_paper_stores_the_pdf_and_a_layout(library_env, fake_embedder, paper_file):
    result = library.add_paper(paper_file)
    assert result.outcome == "added" and result.highlights == "exact"
    stored = pdf_dir(library_env) / f"{result.paper_id}.pdf"
    assert stored.read_bytes() == paper_file.read_bytes()
    layout = json.loads((pdf_dir(library_env) / f"{result.paper_id}.layout.json").read_text(encoding="utf-8"))
    assert layout["paper_id"] == result.paper_id
    assert len(layout["passages"]) == result.passage_count


def test_known_content_with_a_stored_pdf_is_already_present_without_parsing(
    library_env, fake_embedder, paper_file, spies, tmp_path
):
    first = library.add_paper(paper_file)
    copy = tmp_path / "renamed.pdf"
    copy.write_bytes(paper_file.read_bytes())
    spies.update(parse=0, embed=0)
    again = library.add_paper(copy)
    assert again.paper_id == first.paper_id
    assert again.outcome == "already_present" and again.already_present is True
    assert spies == {"parse": 0, "embed": 0}


# --- attaching a PDF to a paper that has none ---


def test_attach_stores_the_pdf_and_maps_highlights_without_embedding(library_env, fake_embedder, paper_file, spies):
    first = library.add_paper(paper_file)
    forget_pdf(library_env, first.paper_id)
    spies.update(parse=0, embed=0)
    result = library.add_paper(paper_file)
    assert result.outcome == "pdf_attached" and result.highlights == "exact"
    assert spies["embed"] == 0 and spies["parse"] == 1
    assert (pdf_dir(library_env) / f"{first.paper_id}.pdf").exists()
    assert (pdf_dir(library_env) / f"{first.paper_id}.layout.json").exists()
    assert not (pdf_dir(library_env) / f"{first.paper_id}.layout-mismatch").exists()
    assert result.passage_count == first.passage_count


def test_attach_with_different_chunking_stores_no_layout_and_marks_a_mismatch(
    library_env, fake_embedder, paper_file, monkeypatch
):
    first = library.add_paper(paper_file)
    forget_pdf(library_env, first.paper_id)
    change_chunking(monkeypatch)
    result = library.add_paper(paper_file)
    assert result.outcome == "pdf_attached" and result.highlights == "mismatch"
    assert (pdf_dir(library_env) / f"{first.paper_id}.pdf").exists()
    assert not (pdf_dir(library_env) / f"{first.paper_id}.layout.json").exists()
    assert (pdf_dir(library_env) / f"{first.paper_id}.layout-mismatch").exists()


# --- passage views (the read path never parses) ---


def first_passage_id(paper_id):
    return f"{paper_id}-0"


def test_get_passage_returns_layout_regions(library_env, fake_embedder, paper_file, spies):
    result = library.add_paper(paper_file)
    spies.update(parse=0)
    view = library.get_passage(first_passage_id(result.paper_id))
    assert spies["parse"] == 0
    assert view.paper_id == result.paper_id and view.title == result.title
    assert view.page >= 1 and view.page_count >= view.page and view.text and view.section
    assert view.has_pdf is True and view.layout_reason is None and view.can_reprocess is False
    assert view.layout is not None and view.layout.regions
    assert {r.page for r in view.layout.regions} <= {p["number"] for p in view.layout.pages}
    assert view.page in {p["number"] for p in view.layout.pages}


def test_get_passage_without_a_pdf_has_no_layout(library_env, fake_embedder, paper_file):
    result = library.add_paper(paper_file)
    forget_pdf(library_env, result.paper_id)
    view = library.get_passage(first_passage_id(result.paper_id))
    assert view.layout is None and view.layout_reason == "no_pdf" and view.has_pdf is False
    assert view.can_reprocess is False


def test_get_passage_after_a_mismatch_offers_reprocessing(library_env, fake_embedder, paper_file, monkeypatch):
    result = library.add_paper(paper_file)
    forget_pdf(library_env, result.paper_id)
    change_chunking(monkeypatch)
    library.add_paper(paper_file)
    view = library.get_passage(first_passage_id(result.paper_id))
    assert view.layout is None and view.layout_reason == "mismatch" and view.can_reprocess is True


def test_get_passage_rejects_an_unknown_id(library_env, fake_embedder):
    with pytest.raises(UnknownPassageError):
        library.get_passage("nope-0")


# --- PDF files ---


def test_pdf_path_points_at_the_stored_copy(library_env, fake_embedder, paper_file):
    result = library.add_paper(paper_file)
    assert library.pdf_path(result.paper_id).read_bytes() == paper_file.read_bytes()


def test_pdf_path_errors(library_env, fake_embedder, paper_file):
    with pytest.raises(UnknownPaperError):
        library.pdf_path("000000000000")
    result = library.add_paper(paper_file)
    forget_pdf(library_env, result.paper_id)
    with pytest.raises(PdfMissingError):
        library.pdf_path(result.paper_id)


def test_delete_removes_the_pdf_layout_and_marker(library_env, fake_embedder, paper_file, monkeypatch):
    result = library.add_paper(paper_file)
    (pdf_dir(library_env) / f"{result.paper_id}.layout-mismatch").write_text("x", encoding="utf-8")
    library.delete_paper(result.paper_id)
    assert list(pdf_dir(library_env).glob(f"{result.paper_id}*")) == []


# --- re-processing a paper from its stored PDF ---


def test_reprocess_rebuilds_passages_and_layout_and_clears_the_marker(
    library_env, fake_embedder, paper_file, monkeypatch
):
    first = library.add_paper(paper_file)
    forget_pdf(library_env, first.paper_id)
    change_chunking(monkeypatch)
    library.add_paper(paper_file)  # mismatch: passages were made with 220/40
    result = library.reprocess_paper(first.paper_id)
    assert result.outcome == "reprocessed" and result.highlights == "exact"
    assert not (pdf_dir(library_env) / f"{first.paper_id}.layout-mismatch").exists()
    view = library.get_passage(first_passage_id(first.paper_id))
    assert view.layout is not None and view.layout_reason is None
    assert result.passage_count == len(store.paper_metadata(first.paper_id))


def test_reprocess_failure_leaves_the_paper_unchanged(library_env, fake_embedder, paper_file, monkeypatch):
    first = library.add_paper(paper_file)
    before = store.paper_metadata(first.paper_id)

    def broken(texts, on_progress=None):
        raise RuntimeError("embedding failed")

    monkeypatch.setattr(store, "embed_passages", broken)
    with pytest.raises(RuntimeError):
        library.reprocess_paper(first.paper_id)
    assert store.paper_metadata(first.paper_id) == before
    assert (pdf_dir(library_env) / f"{first.paper_id}.layout.json").exists()


def test_reprocess_needs_a_stored_pdf(library_env, fake_embedder, paper_file):
    result = library.add_paper(paper_file)
    forget_pdf(library_env, result.paper_id)
    with pytest.raises(PdfMissingError):
        library.reprocess_paper(result.paper_id)
    with pytest.raises(UnknownPaperError):
        library.reprocess_paper("000000000000")
