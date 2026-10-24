"""store.embed_passages progress (spec FR-017, contracts/engine-api.md). No real model."""

import numpy as np
import pytest

from paperpilot import store


class FakeModel:
    """Stands in for SentenceTransformer.encode: one 3-number vector per text."""

    def __init__(self) -> None:
        self.calls: list[int] = []

    def encode(self, texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False):
        texts = [texts] if isinstance(texts, str) else list(texts)
        self.calls.append(len(texts))
        return np.array([[float(len(t)), 0.0, 1.0] for t in texts])


@pytest.fixture
def fake_model(monkeypatch):
    model = FakeModel()
    monkeypatch.setattr(store, "_model", model)
    return model


def test_embed_passages_reports_progress_after_each_batch(fake_model):
    texts = [f"passage {i}" for i in range(70)]
    progress: list[tuple[int, int]] = []
    vectors = store.embed_passages(texts, on_progress=lambda done, total: progress.append((done, total)))
    assert progress == [(32, 70), (64, 70), (70, 70)]
    assert len(vectors) == 70
    assert vectors[0] == [float(len("passage 0")), 0.0, 1.0]
    assert vectors[69] == [float(len("passage 69")), 0.0, 1.0]


def test_embed_passages_without_a_callback_is_unchanged(fake_model):
    texts = [f"passage {i}" for i in range(5)]
    assert store.embed_passages(texts) == [[float(len(t)), 0.0, 1.0] for t in texts]


def test_embed_passages_of_nothing_reports_nothing(fake_model):
    progress: list = []
    assert store.embed_passages([], on_progress=lambda *args: progress.append(args)) == []
    assert progress == []
