"""Shared fixtures: a temporary library, a fake embedder, and generated test PDFs.

Library tests run offline: no embedding model, no network, no real papers. The fake
embedder replaces `store.embed_passages`, `store.embed_query` and `store.load_model`, so
`library` must call them through the `store` module (e.g. `store.embed_query(...)`).
`paperpilot.store` is imported inside fixtures only, so tests that do not use these
fixtures still run when `store` is missing or broken.
"""

import hashlib
import math
import re
from pathlib import Path

import pymupdf
import pytest

EMBED_DIM = 384

DEFAULT_SECTIONS = [
    (
        "Abstract",
        "We study how research papers can be split into passages and searched by meaning. "
        "Our system reads each paper, finds its sections, and stores short passages with "
        "their page numbers so that every search result can be traced back to its source. "
        "We show that simple rules work well on typical conference papers.",
    ),
    (
        "1 Introduction",
        "Researchers read many papers and often need to find one detail quickly. Keyword "
        "search misses passages that use different words for the same idea. Semantic search "
        "compares meanings instead of exact words. In this paper we describe a small local "
        "library that adds papers once and answers natural language questions with passages.",
    ),
    (
        "2 Method",
        "We evaluate the system on a benchmark dataset of questions about five papers. The "
        "evaluation dataset contains questions written by researchers together with the "
        "passages that answer them. Each paper is split into passages of about two hundred "
        "words, embedded with a small model, and stored in a persistent vector database.",
    ),
    (
        "3 Results",
        "The system returns a relevant passage among the first six results for most "
        "questions. Results are best for questions about methods and datasets, and weakest "
        "for questions about numbers inside tables. Adding a paper takes a few seconds on a "
        "laptop processor, and a search over the whole library finishes well under a second.",
    ),
]

REFERENCES = (
    "[1] A. Author and B. Writer. refonlytoken A referenced paper about citations. "
    "Proceedings of a Conference, 2020."
)

PAGE_BOTTOM = 790.0


def write_pdf(
    path: Path,
    sections: list[tuple[str, str]] | None = None,
    references: bool = True,
    blank: bool = False,
    title: str = "A Study of Searching Research Papers by Meaning",
) -> Path:
    """Write a small single-column text PDF with headings, paragraphs and references."""
    doc = pymupdf.open()
    if blank:
        doc.new_page()
        doc.save(path)
        return path

    page = doc.new_page()
    y = 50.0

    def add(text: str, size: float, height: float) -> None:
        nonlocal page, y
        if y + height > PAGE_BOTTOM:
            page = doc.new_page()
            y = 50.0
        rect = pymupdf.Rect(50, y, 545, y + height)
        if page.insert_textbox(rect, text, fontsize=size) < 0:
            raise ValueError(f"text does not fit in its box: {text[:40]!r}")
        y += height + 12

    add(title, 16, 30)
    for heading, body in sections if sections is not None else DEFAULT_SECTIONS:
        add(heading, 12, 24)
        add(body, 10, 110)
    if references:
        add("References", 12, 24)
        add(REFERENCES, 10, 40)

    doc.set_metadata({"title": title})
    doc.save(path)
    return path


@pytest.fixture
def make_pdf():
    """Return `write_pdf(path, sections=None, references=True, blank=False, title=...)`."""
    return write_pdf


@pytest.fixture
def library_env(tmp_path, monkeypatch):
    """Point the library at a fresh temporary folder with default settings."""
    from paperpilot import store

    library_dir = tmp_path / "library"
    for name, value in {
        "CHUNK_WORDS": "220",
        "CHUNK_OVERLAP": "40",
        "MIN_CHUNK_WORDS": "30",
        "TOP_K": "6",
        "EMBED_MODEL": "BAAI/bge-small-en-v1.5",
        "LIBRARY_DIR": str(library_dir),
    }.items():
        monkeypatch.setenv(name, value)
    store.reset_cache()
    yield library_dir
    store.reset_cache()


def fake_vector(text: str) -> list[float]:
    """Deterministic normalised bag-of-words vector; shared words mean higher similarity."""
    vector = [0.0] * EMBED_DIM
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        index = int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBED_DIM
        vector[index] += 1.0
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        vector[0] = 1.0
        return vector
    return [v / norm for v in vector]


@pytest.fixture
def fake_embedder(monkeypatch):
    """Replace the embedding model with `fake_vector` (no download, no torch)."""
    from paperpilot import store

    def embed_passages(texts, on_progress=None):
        vectors = [fake_vector(t) for t in texts]
        if on_progress is not None and texts:
            on_progress(len(texts), len(texts))
        return vectors

    monkeypatch.setattr(store, "load_model", lambda: 0.0)
    monkeypatch.setattr(store, "embed_passages", embed_passages)
    monkeypatch.setattr(store, "embed_query", fake_vector)


TEST_API_KEY = "sk-test-key-123"


@pytest.fixture(autouse=True)
def isolated_library_dir(tmp_path_factory, monkeypatch):
    """Every test gets its own LIBRARY_DIR, so nothing (e.g. usage.sqlite3) touches data/library.

    library_env and other fixtures set their own folder on top of this.
    """
    monkeypatch.setenv("LIBRARY_DIR", str(tmp_path_factory.mktemp("library")))


@pytest.fixture(autouse=True)
def no_real_llm_client(monkeypatch):
    """Fail any test that tries to create a real LLM client (unit tests never call the API)."""
    import openai

    def blocked(*args, **kwargs):
        raise AssertionError("real LLM client created in a unit test")

    monkeypatch.setattr(openai, "OpenAI", blocked)
    try:
        from paperpilot import llm
    except ImportError:  # llm.py not written yet
        return
    monkeypatch.setattr(llm, "_make_client", blocked)

    def no_key_endpoint(*args, **kwargs):
        raise AssertionError("the provider's key endpoint was called in a unit test")

    # Usage refreshes read OpenRouter's key endpoint; tests that need it stub it (ADR-0007).
    monkeypatch.setattr(llm, "_fetch_key_info", no_key_endpoint, raising=False)


@pytest.fixture
def llm_env(monkeypatch):
    """Default LLM settings with a dummy key; a real .env cannot override them."""
    for name, value in {
        "LLM_PROVIDER": "openrouter",
        "LLM_BASE_URL": "",
        "LLM_API_KEY": TEST_API_KEY,
        "LLM_MODEL": "test/model:free",
        "LLM_REASONING_EFFORT": "",
    }.items():
        monkeypatch.setenv(name, value)
    return TEST_API_KEY


class ScriptedLLM:
    """Stands in for llm.generate: returns queued replies (str or LLMReply) or raises queued errors.

    A queued object with `wait_seconds` (an llm.RetryNotice) is passed to the caller's `on_retry`
    instead, simulating a retry wait before the next queued reply.
    """

    def __init__(self) -> None:
        self.queue: list = []
        self.calls: list[tuple[str, str]] = []

    def add(self, *items) -> None:
        """Queue replies: a str becomes an LLMReply with 100 input and 40 output tokens."""
        self.queue.extend(items)

    def __call__(self, system: str, prompt: str, on_retry=None):
        from paperpilot.llm import LLMReply

        self.calls.append((system, prompt))
        if not self.queue:
            raise AssertionError("no scripted LLM reply left")
        item = self.queue.pop(0)
        while hasattr(item, "wait_seconds"):
            if on_retry is not None:
                on_retry(item)
            if not self.queue:
                raise AssertionError("no scripted LLM reply left after a retry notice")
            item = self.queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, str):
            return LLMReply(item, 100, 40, None, 1, 0.01)
        return item


@pytest.fixture
def fake_answers(monkeypatch):
    """Replace llm.generate with a ScriptedLLM (service must call it as llm.generate)."""
    from paperpilot import llm

    scripted = ScriptedLLM()
    monkeypatch.setattr(llm, "generate", scripted)
    return scripted


@pytest.fixture
def answer_env(tmp_path, make_pdf, library_env, fake_embedder, llm_env, fake_answers, monkeypatch):
    """A temporary library with one generated paper, threshold 0 and a scripted LLM."""
    from paperpilot.library import add_paper

    monkeypatch.setenv("RELEVANCE_THRESHOLD", "0.0")
    paper = add_paper(make_pdf(tmp_path / "paper.pdf"))
    return paper


# --- Feature 4: summaries and comparison ---

SUMMARY_TITLE = "Low-Rank Updates for Efficient Model Adaptation"

# One section per summary facet (problem, method, data, results, limitations), each long enough
# to be its own passage with the default chunking, so a facet search has passages to rank.
SUMMARY_SECTIONS = [
    (
        "Abstract",
        "Fine-tuning every parameter of a very large language model is expensive, because each "
        "downstream task needs its own full copy of the model. We address this problem with a "
        "method that freezes the pretrained weights and trains only small low-rank update "
        "matrices injected into each layer, so many tasks can share one base model.",
    ),
    (
        "1 Introduction",
        "Large pretrained models are adapted to many tasks, but storing and serving a separate "
        "fine-tuned copy for every task is prohibitively costly in memory and storage. The "
        "research question is whether a small number of trainable parameters per task can match "
        "full fine-tuning quality while keeping inference as fast as the original model.",
    ),
    (
        "2 Method",
        "The proposed method keeps the pretrained weight matrix frozen and expresses its update "
        "as the product of two small matrices B and A of low rank r. Matrix B starts at zero, so "
        "training begins from the original model. After training the product can be merged into "
        "the frozen weights, which adds no inference latency compared with the base model.",
    ),
    (
        "3 Experiments",
        "We evaluate on the GLUE benchmark with RoBERTa and DeBERTa, on the E2E NLG Challenge "
        "dataset with GPT-2, and on WikiSQL, MNLI and SAMSum with GPT-3. Each dataset uses its "
        "standard training split, and every method is tuned with the same validation protocol "
        "so that the comparisons with baselines are fair across all experimental settings.",
    ),
    (
        "4 Results",
        "The method matches or exceeds full fine-tuning on GPT-3 175B while training a small "
        "fraction of the parameters. It reduces the number of trainable parameters by about "
        "10,000 times and the GPU memory requirement by about 3 times. Throughput during "
        "training is higher, and no additional latency is introduced at inference time.",
    ),
    (
        "5 Limitations",
        "A limitation is that batching inputs for different tasks in one forward pass is not "
        "straightforward when the low-rank matrices are merged into the weights to avoid extra "
        "latency. Choosing which weight matrices to adapt is also guided by heuristics, and the "
        "rank r must be selected per task, which we leave to future work on automatic selection.",
    ),
]

SECOND_TITLE = "A Retrieval Benchmark for Open-Domain Questions"

# A second paper with no limitations section, for comparisons and not-reported cells.
SECOND_SECTIONS = [
    (
        "Abstract",
        "Open-domain question answering systems must find evidence in a large corpus before "
        "answering. We study the problem of retrieving relevant passages for factual questions "
        "and introduce a benchmark that measures how often the evidence is found among the first "
        "results returned by a retriever for questions written by annotators.",
    ),
    (
        "1 Method",
        "Our retriever encodes questions and passages with two separate transformer encoders "
        "and ranks passages by the inner product of their embeddings. The passage index covers "
        "a full Wikipedia dump split into one hundred word blocks, and the encoders are trained "
        "with in-batch negatives taken from the other questions in the same training batch.",
    ),
    (
        "2 Datasets",
        "We train and evaluate on Natural Questions, TriviaQA and WebQuestions, using the "
        "standard splits. Each question is paired with gold evidence passages from Wikipedia, and "
        "a question counts as answered when one of the retrieved passages contains the answer "
        "string exactly, following the evaluation protocol used by earlier retrieval work.",
    ),
    (
        "3 Results",
        "The dense retriever finds the answer passage among the top twenty results for 79 "
        "percent of Natural Questions, compared with 59 percent for a keyword baseline. Gains "
        "are largest for questions that paraphrase the evidence, where keyword overlap is low, "
        "and smallest for questions that name rare entities appearing in a single passage.",
    ),
]


@pytest.fixture
def summary_paper(tmp_path, make_pdf):
    """Path of a generated paper with one section per summary facet."""
    return make_pdf(tmp_path / "summary-paper.pdf", sections=SUMMARY_SECTIONS, references=False,
                    title=SUMMARY_TITLE)


@pytest.fixture
def second_paper(tmp_path, make_pdf):
    """Path of a second generated paper (no limitations section)."""
    return make_pdf(tmp_path / "second-paper.pdf", sections=SECOND_SECTIONS, references=False,
                    title=SECOND_TITLE)


@pytest.fixture
def summary_env(summary_paper, library_env, fake_embedder, llm_env, fake_answers, monkeypatch):
    """The summary paper in a temporary library, threshold 0 and a scripted LLM; returns its AddResult."""
    from paperpilot.library import add_paper

    monkeypatch.setenv("RELEVANCE_THRESHOLD", "0.0")
    return add_paper(summary_paper)
