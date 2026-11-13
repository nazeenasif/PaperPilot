"""The `retrieval` command and its result file (spec FR-006, FR-008, FR-027, SC-002, SC-009;
research R11). A fixture library with the fake embedder; no model, no network."""

import json

import pytest

from evaluation import __main__ as cli
from paperpilot import library, llm

ARXIV = "2401.00001"
PHRASE = "large corpus of abstracts"


@pytest.fixture
def files(eval_paper, tmp_path, monkeypatch):
    def no_requests(*args, **kwargs):
        raise AssertionError("retrieval must not call the model")

    monkeypatch.setattr(llm, "generate", no_requests)
    questions = [
        {"id": "s1", "kind": "single", "question": "Which corpus is used for pre-training?", "scope": "library",
         "papers": [ARXIV], "expected": "Abstracts.", "table": False, "confirmed": True,
         "evidence": [{"paper": ARXIV, "page": 1, "phrase": PHRASE}]},
        {"id": "n1", "kind": "near_miss", "question": "What is the capital of Peru?", "scope": "library",
         "papers": [ARXIV], "expected": "not_found", "table": False, "confirmed": True, "evidence": []},
    ]
    golden = tmp_path / "golden.json"
    golden.write_text(json.dumps({"version": 3, "papers": [ARXIV], "questions": questions}), encoding="utf-8")
    experiments = tmp_path / "experiments.json"
    experiments.write_text(json.dumps({"experiments": [
        {"name": "baseline", "changes": {}, "answers": True},
        {"name": "gemma", "changes": {"answer_model": "google/gemma-4-31b-it:free"}, "answers": True, "optional": True},
    ]}), encoding="utf-8")
    return {"golden": golden, "experiments": experiments, "results": tmp_path / "results", "paper": eval_paper}


def run(files, *names):
    return cli.main(["retrieval", *names, "--golden", str(files["golden"]), "--experiments",
                     str(files["experiments"]), "--results", str(files["results"])])


def test_retrieval_baseline_writes_its_result_file(files, capsys):
    assert run(files, "baseline") == 0
    result = json.loads((files["results"] / "baseline.json").read_text(encoding="utf-8"))
    assert result["experiment"] == "baseline"
    assert result["configuration"]["retrieval"] == {"method": "vector", "shortlist": 20}
    assert result["configuration"]["golden"]["version"] == 3 and len(result["configuration"]["golden"]["sha256"]) == 64
    assert result["retrieval"]["hit@6"] == 1.0 and result["retrieval"]["gated_not_found"]["of"] == 1
    assert [q["id"] for q in result["questions"]] == ["s1", "n1"]
    assert result["answers"] is None and result["requests"] == {"planned": 0, "retries": 0}
    assert "hit@6" in capsys.readouterr().out


def test_the_result_file_holds_no_passage_text(files):
    run(files, "baseline")
    text = (files["results"] / "baseline.json").read_text(encoding="utf-8")
    assert PHRASE not in text and "fine-tuning stage" not in text


def test_a_repeat_run_gives_the_same_numbers(files):
    run(files, "baseline")
    first = json.loads((files["results"] / "baseline.json").read_text(encoding="utf-8"))
    run(files, "baseline")
    second = json.loads((files["results"] / "baseline.json").read_text(encoding="utf-8"))
    assert {k: v for k, v in first["retrieval"].items() if k != "latency_s"} == \
           {k: v for k, v in second["retrieval"].items() if k != "latency_s"}
    assert first["questions"] == second["questions"]


def test_the_library_is_unchanged(files, library_env):
    paper_id = files["paper"].paper_id
    before = library.passage_fingerprint(paper_id)
    run(files, "baseline")
    assert library.passage_fingerprint(paper_id) == before
    assert not (library_env / library.RESULTS_FILE).exists()


def test_an_answer_only_experiment_is_refused(files, capsys):
    assert run(files, "gemma") == 2
    assert "not a retrieval experiment" in capsys.readouterr().out
    assert not (files["results"] / "gemma.json").exists()


def test_an_unknown_experiment_is_refused(files, capsys):
    assert run(files, "nonsense") == 2
    assert "unknown experiment" in capsys.readouterr().out


def test_with_no_names_every_retrieval_experiment_runs(files):
    assert run(files) == 0
    assert sorted(p.name for p in files["results"].iterdir()) == ["baseline.json"]
