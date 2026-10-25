"""Saved summaries and comparisons in <LIBRARY_DIR>/results.sqlite3 (research R6, ADR-0009).

The key is the identity (kind, papers, aspects); model, prompt version and each paper's passage
fingerprint are stored with the row and compared on lookup, so an old result is found and
reported as stale rather than lost.
"""

import multiprocessing
import os

import pytest

from paperpilot import library, store

MODEL = "test/model:free"


@pytest.fixture
def two_papers(summary_env, second_paper):
    second = library.add_paper(second_paper)
    return summary_env.paper_id, second.paper_id


def test_a_saved_result_round_trips(summary_env, library_env):
    key = library.result_key("summary", [summary_env.paper_id])
    library.save_result(key, {"answer": 42}, model=MODEL, prompt_version=1)
    assert library.load_result(key, model=MODEL, prompt_version=1) == ({"answer": 42}, None)
    assert (library_env / "results.sqlite3").exists()


def test_nothing_saved_is_none(summary_env):
    assert library.load_result(library.result_key("summary", [summary_env.paper_id]), MODEL, 1) is None


def test_keys_ignore_order(two_papers):
    a, b = two_papers
    assert library.result_key("comparison", [a, b], ["method", "results"]) == \
        library.result_key("comparison", [b, a], ["results", "method"])
    assert library.result_key("summary", [a]) != library.result_key("comparison", [a])


def test_saving_again_replaces_the_result(summary_env):
    key = library.result_key("summary", [summary_env.paper_id])
    library.save_result(key, {"v": 1}, MODEL, 1)
    library.save_result(key, {"v": 2}, MODEL, 1)
    assert library.load_result(key, MODEL, 1) == ({"v": 2}, None)


@pytest.mark.parametrize(
    ("model", "version", "reason"),
    [("other/model:free", 1, "model_changed"), (MODEL, 2, "instructions_changed")],
)
def test_a_result_from_another_model_or_version_is_stale(summary_env, model, version, reason):
    key = library.result_key("summary", [summary_env.paper_id])
    library.save_result(key, {"v": 1}, MODEL, 1)
    assert library.load_result(key, model, version) == ({"v": 1}, reason)


def test_changed_passages_make_a_result_stale(summary_env, monkeypatch):
    key = library.result_key("summary", [summary_env.paper_id])
    library.save_result(key, {"v": 1}, MODEL, 1)
    real = store.paper_passages
    monkeypatch.setattr(store, "paper_passages", lambda pid: [(i, t + " edited") for i, t in real(pid)])
    assert library.load_result(key, MODEL, 1) == ({"v": 1}, "passages_changed")


def test_the_fingerprint_is_stable_and_follows_the_passages(summary_env, monkeypatch):
    first = library.passage_fingerprint(summary_env.paper_id)
    assert library.passage_fingerprint(summary_env.paper_id) == first and len(first) == 64
    real = store.paper_passages
    monkeypatch.setattr(store, "paper_passages", lambda pid: [(i, t.upper()) for i, t in real(pid)])
    assert library.passage_fingerprint(summary_env.paper_id) != first


def test_deleting_a_paper_forgets_every_result_that_includes_it(two_papers):
    a, b = two_papers
    library.save_result(library.result_key("summary", [a]), {"s": "a"}, MODEL, 1)
    library.save_result(library.result_key("summary", [b]), {"s": "b"}, MODEL, 1)
    library.save_result(library.result_key("comparison", [a, b], ["method"]), {"c": 1}, MODEL, 1)
    library.delete_paper(a)
    assert library.load_result(library.result_key("summary", [a]), MODEL, 1) is None
    assert library.load_result(library.result_key("comparison", [a, b], ["method"]), MODEL, 1) is None
    assert library.load_result(library.result_key("summary", [b]), MODEL, 1) is not None


def test_reprocessing_a_paper_forgets_its_results(two_papers):
    a, b = two_papers
    library.save_result(library.result_key("summary", [a]), {"s": "a"}, MODEL, 1)
    library.save_result(library.result_key("summary", [b]), {"s": "b"}, MODEL, 1)
    library.reprocess_paper(a)
    assert library.load_result(library.result_key("summary", [a]), MODEL, 1) is None
    assert library.load_result(library.result_key("summary", [b]), MODEL, 1) is not None


def test_forget_results_returns_the_count(two_papers):
    a, b = two_papers
    library.save_result(library.result_key("summary", [a]), {}, MODEL, 1)
    library.save_result(library.result_key("comparison", [a, b], ["method"]), {}, MODEL, 1)
    assert library.forget_results(a) == 2 and library.forget_results(a) == 0


def save_in_another_process(library_dir: str, paper_id: str, offset: int) -> None:
    """Runs in a spawned process: save 10 results under distinct aspects for the same paper."""
    os.environ["LIBRARY_DIR"] = library_dir
    from paperpilot import library as child

    child.passage_fingerprint = lambda pid: "fixed"
    for i in range(10):
        child.save_result(child.result_key("comparison", [paper_id], [f"aspect-{offset + i}"]), {"i": i}, MODEL, 1)


def test_two_processes_saving_at_once_lose_nothing(summary_env, library_env, monkeypatch):
    context = multiprocessing.get_context("spawn")
    processes = [context.Process(target=save_in_another_process,
                                 args=(str(library_env), summary_env.paper_id, offset)) for offset in (0, 100)]
    for p in processes:
        p.start()
    for p in processes:
        p.join(timeout=120)
        assert p.exitcode == 0
    monkeypatch.setattr(library, "passage_fingerprint", lambda pid: "fixed")
    found = [library.load_result(library.result_key("comparison", [summary_env.paper_id], [f"aspect-{n}"]), MODEL, 1)
             for n in [*range(10), *range(100, 110)]]
    assert all(f is not None for f in found)
