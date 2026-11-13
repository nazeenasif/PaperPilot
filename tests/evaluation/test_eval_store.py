"""The evaluation cache, `data/eval/eval.sqlite3` (research R11, data-model.md): stored answers,
claim verdicts and run progress. No model and no network."""

import multiprocessing

import pytest

from evaluation import store


@pytest.fixture
def cache(tmp_path):
    return store.EvalStore(tmp_path)


def test_the_file_lives_under_data_eval(cache, tmp_path):
    cache.save_answer("cfg", "q1", 0, {"text": "A."})
    assert (tmp_path / "data" / "eval" / "eval.sqlite3").exists()


def test_an_answer_is_found_by_configuration_question_and_run(cache):
    cache.save_answer("cfg", "q1", 0, {"text": "A."})
    assert cache.load_answer("cfg", "q1", 0) == {"text": "A."}
    assert cache.load_answer("cfg", "q1", 1) is None
    assert cache.load_answer("other", "q1", 0) is None
    assert cache.load_answer("cfg", "q2", 0) is None


def test_saving_an_answer_again_replaces_it(cache):
    cache.save_answer("cfg", "q1", 0, {"text": "A."})
    cache.save_answer("cfg", "q1", 0, {"text": "B."})
    assert cache.load_answer("cfg", "q1", 0) == {"text": "B."}


def test_a_verdict_is_found_by_its_key(cache):
    cache.save_verdict("key", {"verdict": "supported", "reason": "It says so."})
    assert cache.load_verdict("key") == {"verdict": "supported", "reason": "It says so."}
    assert cache.load_verdict("other") is None


def test_a_not_judged_verdict_is_never_returned_as_final(cache):
    cache.save_verdict("key", {"verdict": "not_judged", "reason": "unreadable"})
    assert cache.load_verdict("key") is None


def test_progress_records_plan_units_and_sessions(cache):
    session = cache.start_session("baseline", "answers", slice_size=30)
    cache.set_planned("baseline", "answers", 43)
    cache.record_unit("baseline", "answers", planned=1, retries=0)
    cache.record_unit("baseline", "answers", planned=2, retries=1)
    cache.end_session(session, "slice")
    progress = cache.progress("baseline", "answers")
    assert (progress["planned"], progress["done"]) == (43, 2)
    assert progress["requests"] == {"planned": 3, "retries": 1}
    assert [(s["slice"], s["used"], s["ended_by"]) for s in progress["sessions"]] == [(30, 4, "slice")]


def test_progress_starts_empty(cache):
    assert cache.progress("baseline", "judge") == {
        "planned": 0, "done": 0, "requests": {"planned": 0, "retries": 0}, "sessions": [],
    }


def test_everything_survives_reopening(tmp_path):
    first = store.EvalStore(tmp_path)
    first.save_answer("cfg", "q1", 0, {"text": "A."})
    first.save_verdict("key", {"verdict": "partly", "reason": "Scope."})
    first.set_planned("baseline", "answers", 5)
    again = store.EvalStore(tmp_path)
    assert again.load_answer("cfg", "q1", 0) == {"text": "A."}
    assert again.load_verdict("key")["verdict"] == "partly"
    assert again.progress("baseline", "answers")["planned"] == 5


def write_many(root, offset):
    cache = store.EvalStore(__import__("pathlib").Path(root))
    for n in range(20):
        cache.save_answer("cfg", f"q{offset + n}", 0, {"n": offset + n})
        cache.record_unit("baseline", "answers", planned=1, retries=0)


def test_two_processes_writing_at_once_lose_nothing(tmp_path):
    context = multiprocessing.get_context("spawn")
    processes = [context.Process(target=write_many, args=(str(tmp_path), offset)) for offset in (0, 100)]
    for p in processes:
        p.start()
    for p in processes:
        p.join(timeout=120)
        assert p.exitcode == 0
    cache = store.EvalStore(tmp_path)
    assert all(cache.load_answer("cfg", f"q{n}", 0) == {"n": n} for n in [*range(20), *range(100, 120)])
    assert cache.progress("baseline", "answers")["done"] == 40
