"""The prefix experiment's own library (research R6): built from the PDFs under its own
LIBRARY_DIR, counted against the main library's usage, reused, and never touching the main
library. Fake embedder; no model, no network."""

import pytest

from evaluation import libraries
from paperpilot import library, store
from paperpilot.config import load_settings


@pytest.fixture
def papers_dir(tmp_path, make_pdf):
    folder = tmp_path / "papers"
    folder.mkdir()
    make_pdf(folder / "one.pdf", title="Paper One")
    return folder


def test_the_prefix_library_is_built_in_its_own_folder(tmp_path, papers_dir, library_env, fake_embedder, monkeypatch):
    seen = []
    real = library.add_paper

    def spy(path, on_progress=None):
        s = load_settings()
        seen.append((s.library_dir.resolve(), s.usage_dir.resolve(), s.embed_prefix))
        return real(path, on_progress)

    monkeypatch.setattr(library, "add_paper", spy)
    root = tmp_path / "eval" / "libraries" / "prefix"
    libraries.build_prefix_library(root, papers_dir)
    assert seen == [(root.resolve(), library_env.resolve(), True)]
    with libraries.using_library(root, embed_prefix=True):
        assert [p.title for p in library.list_papers()] == ["Paper One"]
    assert load_settings().library_dir.resolve() == library_env.resolve()
    assert library.list_papers() == []  # the main library is unchanged


def test_a_built_library_is_reused(tmp_path, papers_dir, library_env, fake_embedder, monkeypatch):
    root = tmp_path / "prefix"
    libraries.build_prefix_library(root, papers_dir)
    calls = []
    monkeypatch.setattr(library, "add_paper", lambda *a, **k: calls.append(a))
    libraries.build_prefix_library(root, papers_dir)
    assert calls == []


def test_a_changed_setting_rebuilds_it(tmp_path, papers_dir, library_env, fake_embedder, monkeypatch):
    root = tmp_path / "prefix"
    libraries.build_prefix_library(root, papers_dir)
    monkeypatch.setenv("CHUNK_WORDS", "180")
    store.reset_cache()
    calls = []
    real = library.add_paper
    monkeypatch.setattr(library, "add_paper", lambda path, on_progress=None: calls.append(path) or real(path, on_progress))
    libraries.build_prefix_library(root, papers_dir)
    assert len(calls) == 1


def test_the_main_library_cannot_be_the_prefix_library(tmp_path, papers_dir, library_env, fake_embedder):
    with pytest.raises(ValueError):
        libraries.build_prefix_library(library_env, papers_dir)
