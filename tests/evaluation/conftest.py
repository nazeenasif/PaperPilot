"""Fixtures for the evaluation harness tests. The root `tests/conftest.py` fixtures (temporary
library, fake embedder, scripted LLM) apply here too. Nothing here can reach the model, the
provider or the Hugging Face hub.

No __init__.py in tests/evaluation: as a package it would be imported as "evaluation" and shadow
the real package under test (as tests/api)."""

import pytest

EVAL_ARXIV = "2401.00001"
EVAL_SECTIONS = [
    ("1 Method",
     "We propose a retrieval method for scientific papers. arXiv:2401.00001 The pre-training stage uses a "
     "large corpus of abstracts, and the fine-tuning stage adapts the encoder to questions written by "
     "readers of each paper."),
    ("2 Results",
     "Our method reaches the best accuracy on every benchmark we tried, and it is faster to train than the "
     "baselines, which we describe in the text that follows this short paragraph about the results."),
    ("3 Tables", "Model Acc F1 Base 81.6 79.2 Large 86.6 84.3 Ours 91.7 90.1 Prior 73.7 70.4"),
]


@pytest.fixture
def eval_paper(tmp_path, make_pdf, library_env, fake_embedder):
    """One generated paper (arXiv 2401.00001) in a temporary library with the fake embedder."""
    from paperpilot import library

    path = make_pdf(tmp_path / "eval-paper.pdf", references=False, title="A Study of Golden Questions",
                    sections=EVAL_SECTIONS)
    return library.add_paper(path)
