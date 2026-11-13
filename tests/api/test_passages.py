"""GET /api/passages/{id} and GET /api/papers/{id}/pdf (contracts/web-api.md, spec FR-012–FR-015)."""

import pytest

from paperpilot import ingest, library

FRONTEND = "http://127.0.0.1:3000"
VIEW_FIELDS = {
    "passage_id", "paper_id", "title", "section", "page", "page_count", "kind", "text", "has_pdf",
    "layout", "layout_reason", "can_reprocess",
}


def forget_pdf(api_env, paper_id):
    for path in (api_env["library_dir"] / "pdfs").glob(f"{paper_id}*"):
        path.unlink()


@pytest.fixture
def paper(client_with_paper):
    return client_with_paper.paper


def test_passage_view_has_layout_regions(client_with_paper, paper):
    response = client_with_paper.get(f"/api/passages/{paper.paper_id}-0")
    assert response.status_code == 200
    view = response.json()
    assert set(view) == VIEW_FIELDS
    assert view["paper_id"] == paper.paper_id and view["title"] == paper.title
    assert view["has_pdf"] is True and view["layout_reason"] is None and view["can_reprocess"] is False
    layout = view["layout"]
    assert layout["regions"] and set(layout["regions"][0]) == {"page", "x0", "y0", "x1", "y1"}
    assert {p["number"] for p in layout["pages"]} >= {view["page"]}
    assert set(layout["pages"][0]) == {"number", "width", "height"}


def test_passage_view_without_a_pdf(client_with_paper, paper, api_env):
    forget_pdf(api_env, paper.paper_id)
    view = client_with_paper.get(f"/api/passages/{paper.paper_id}-0").json()
    assert view["layout"] is None and view["layout_reason"] == "no_pdf" and view["has_pdf"] is False


def test_passage_view_after_a_mismatch_offers_reprocessing(client_with_paper, paper, api_env, tmp_path, monkeypatch):
    forget_pdf(api_env, paper.paper_id)
    monkeypatch.setenv("CHUNK_WORDS", "30")
    monkeypatch.setenv("CHUNK_OVERLAP", "5")
    monkeypatch.setenv("MIN_CHUNK_WORDS", "5")
    library.add_paper(tmp_path / "paper.pdf")  # same file: attaches with a mismatched layout
    view = client_with_paper.get(f"/api/passages/{paper.paper_id}-0").json()
    assert view["layout"] is None and view["layout_reason"] == "mismatch" and view["can_reprocess"] is True


def test_unknown_passage_is_a_404(client_with_paper):
    response = client_with_paper.get("/api/passages/nope-0")
    assert response.status_code == 404
    assert response.json() == {"kind": "unknown_passage", "passage_id": "nope-0"}


def test_passage_view_never_parses(client_with_paper, paper, monkeypatch):
    calls = []
    monkeypatch.setattr(ingest, "parse_pdf", lambda *a, **k: calls.append(a))
    client_with_paper.get(f"/api/passages/{paper.paper_id}-0")
    assert calls == []


def test_pdf_is_served_inline(client_with_paper, paper, tmp_path):
    response = client_with_paper.get(f"/api/papers/{paper.paper_id}/pdf", headers={"Origin": FRONTEND})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline")
    assert response.headers.get("access-control-allow-origin") == FRONTEND
    assert response.content == (tmp_path / "paper.pdf").read_bytes()


def test_missing_pdf_is_a_404(client_with_paper, paper, api_env):
    forget_pdf(api_env, paper.paper_id)
    response = client_with_paper.get(f"/api/papers/{paper.paper_id}/pdf")
    assert response.status_code == 404
    assert response.json() == {"kind": "pdf_missing", "paper_id": paper.paper_id}


def test_unknown_paper_pdf_is_a_404(client_with_paper):
    response = client_with_paper.get("/api/papers/000000000000/pdf")
    assert response.status_code == 404
    assert response.json() == {"kind": "unknown_paper", "paper_id": "000000000000"}
