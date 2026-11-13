"""EMBED_PREFIX (Feature 5, research R6): passages are embedded as "title. section. text" while
their stored text, IDs and fingerprint stay the same. Fake embedder; no model, no network."""

import pytest

from paperpilot import library, store


@pytest.fixture
def embedded(monkeypatch, fake_embedder):
    """Record every text sent to store.embed_passages."""
    seen = []
    real = store.embed_passages

    def spy(texts, on_progress=None):
        seen.extend(texts)
        return real(texts, on_progress=on_progress)

    monkeypatch.setattr(store, "embed_passages", spy)
    return seen


def test_with_the_prefix_on_passages_are_embedded_with_title_and_section(tmp_path, make_pdf, library_env,
                                                                         embedded, monkeypatch):
    monkeypatch.setenv("EMBED_PREFIX", "true")
    added = library.add_paper(make_pdf(tmp_path / "p.pdf", title="A Prefix Paper"))
    stored = store.paper_passages(added.paper_id)
    metas = store.paper_metadata(added.paper_id)
    assert len(embedded) == len(stored)
    for text, (_, stored_text), meta in zip(embedded, stored, metas):
        assert text == f"{meta['title']}. {meta['section']}. {stored_text}"


def test_the_stored_passages_and_fingerprint_do_not_change(tmp_path, make_pdf, fake_embedder, monkeypatch):
    pdf = make_pdf(tmp_path / "p.pdf", title="A Prefix Paper")
    fingerprints, passages = [], []
    for name, prefix in (("plain", "false"), ("prefixed", "true")):
        monkeypatch.setenv("LIBRARY_DIR", str(tmp_path / name))
        monkeypatch.setenv("EMBED_PREFIX", prefix)
        store.reset_cache()
        added = library.add_paper(pdf)
        passages.append(store.paper_passages(added.paper_id))
        fingerprints.append(library.passage_fingerprint(added.paper_id))
    store.reset_cache()
    assert passages[0] == passages[1] and fingerprints[0] == fingerprints[1]


def test_the_prefix_is_off_by_default(tmp_path, make_pdf, library_env, embedded, monkeypatch):
    monkeypatch.delenv("EMBED_PREFIX", raising=False)
    added = library.add_paper(make_pdf(tmp_path / "p.pdf"))
    assert embedded == [text for _, text in store.paper_passages(added.paper_id)]


def test_reprocessing_uses_the_prefix_too(tmp_path, make_pdf, library_env, embedded, monkeypatch):
    monkeypatch.setenv("EMBED_PREFIX", "true")
    added = library.add_paper(make_pdf(tmp_path / "p.pdf", title="A Prefix Paper"))
    embedded.clear()
    library.reprocess_paper(added.paper_id)
    assert embedded and all(text.startswith("A Prefix Paper. ") for text in embedded)
