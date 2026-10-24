"""add_paper progress phases and the per-paper statistics on cards (spec FR-017, FR-019)."""

import pytest

from paperpilot import library, store
from test_ingest_layout import FILLER, write_layout_pdf


def recorder():
    events: list[tuple[str, int | None]] = []
    return events, lambda phase, percent: events.append((phase, percent))


def phases(events):
    seen: list[str] = []
    for phase, _ in events:
        if not seen or seen[-1] != phase:
            seen.append(phase)
    return seen


@pytest.fixture
def paper_file(tmp_path, make_pdf):
    return make_pdf(tmp_path / "paper.pdf")


# --- progress phases ---


def test_adding_a_paper_reports_parsing_chunking_embedding_ready(library_env, fake_embedder, paper_file):
    events, on_progress = recorder()
    library.add_paper(paper_file, on_progress=on_progress)
    assert phases(events) == ["parsing", "chunking", "embedding", "ready"]
    percents = [p for phase, p in events if phase == "embedding"]
    assert percents[0] == 0 and percents[-1] == 100
    assert percents == sorted(percents)
    assert all(p is None for phase, p in events if phase != "embedding")


def test_attaching_a_pdf_reports_mapping_then_ready(library_env, fake_embedder, paper_file):
    first = library.add_paper(paper_file)
    for path in (library_env / "pdfs").glob(f"{first.paper_id}*"):
        path.unlink()
    events, on_progress = recorder()
    library.add_paper(paper_file, on_progress=on_progress)
    assert phases(events) == ["mapping", "ready"]


def test_known_content_with_a_pdf_reports_only_ready(library_env, fake_embedder, paper_file):
    library.add_paper(paper_file)
    events, on_progress = recorder()
    library.add_paper(paper_file, on_progress=on_progress)
    assert events == [("ready", None)]


def test_reprocessing_reports_the_usual_phases(library_env, fake_embedder, paper_file):
    added = library.add_paper(paper_file)
    events, on_progress = recorder()
    library.reprocess_paper(added.paper_id, on_progress=on_progress)
    assert phases(events) == ["parsing", "chunking", "embedding", "ready"]


# --- card statistics ---


def test_list_papers_fills_the_card_statistics(library_env, fake_embedder, paper_file):
    added = library.add_paper(paper_file)
    (summary,) = library.list_papers()
    metadata = store.paper_metadata(added.paper_id)
    assert summary.passage_count == len(metadata)
    assert summary.text_passages + summary.table_passages == summary.passage_count
    assert summary.table_passages == sum(1 for m in metadata if m["kind"] == "table")
    assert summary.section_count == len({m["section"] for m in metadata})
    assert summary.section_count >= 3
    assert summary.has_pdf is True and summary.highlights == "exact"
    assert summary.arxiv_id is None


def test_list_papers_reports_no_pdf_for_papers_added_before_feature_3(library_env, fake_embedder, paper_file):
    added = library.add_paper(paper_file)
    for path in (library_env / "pdfs").glob(f"{added.paper_id}*"):
        path.unlink()
    (summary,) = library.list_papers()
    assert summary.has_pdf is False and summary.highlights == "no_pdf"


def test_list_papers_reads_the_arxiv_id_from_the_stored_first_page(library_env, fake_embedder, tmp_path):
    path = write_layout_pdf(tmp_path / "arxiv.pdf", [[
        ("A Paper Posted On The Preprint Server", 16, 30),
        ("arXiv:2106.09685v2 [cs.CL] 16 Oct 2021", 9, 20),
        (FILLER + " written by the authors listed here.", 10, 70),
        ("1 Introduction", 12, 24),
        (FILLER + " the introduction continues.", 10, 70),
    ]])
    added = library.add_paper(path)
    for pdf in (library_env / "pdfs").glob(f"{added.paper_id}*"):
        pdf.unlink()  # the identifier must come from stored passages, not the PDF
    (summary,) = library.list_papers()
    assert summary.arxiv_id == "2106.09685"
