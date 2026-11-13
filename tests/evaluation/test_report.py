"""The generated results table (spec FR-028, FR-029, SC-008; research R11): built from result
files, the experiments file and the golden file only; no cache, no PDFs, no model."""

import hashlib
import json

import pytest

from evaluation import report

GOLDEN = {"version": 1, "note": "Questions drafted by Claude Code, reviewed by Nazeen Asif.",
          "papers": ["1111.11111"], "questions": [
              {"id": "s1", "kind": "single"}, {"id": "s2", "kind": "single"}, {"id": "n1", "kind": "near_miss"}]}


def result(name, sha, hit6=0.5, mrr=0.25, self_graded=False):
    return {
        "experiment": name,
        "configuration": {"golden": {"version": 1, "sha256": sha, "questions": 3}},
        "retrieval": {"hit@1": 0.0, "hit@3": 0.5, "hit@6": hit6, "hit@10": 1.0, "mrr": mrr, "answerable": 2,
                      "per_kind": {"single": {"hit@1": 0.0, "hit@3": 0.5, "hit@6": hit6, "hit@10": 1.0, "mrr": mrr,
                                              "answerable": 2},
                                   "near_miss": {"questions": 1, "gated": 0}},
                      "gated_not_found": {"gated": 0, "of": 1}, "latency_s": 0.2},
        "answers": None, "requests": {"planned": 0, "retries": 0}, "self_graded": self_graded,
        "questions": [{"id": "s1", "kind": "single", "rank": 2, "gate_score": 0.8, "gated": False},
                      {"id": "s2", "kind": "single", "rank": None, "gate_score": 0.7, "gated": False},
                      {"id": "n1", "kind": "near_miss", "rank": None, "gate_score": 0.6, "gated": False}],
    }


@pytest.fixture
def files(tmp_path):
    golden = tmp_path / "golden.json"
    golden.write_text("// a comment\n" + json.dumps(GOLDEN), encoding="utf-8")
    sha = hashlib.sha256(golden.read_bytes()).hexdigest()
    results = tmp_path / "results"
    results.mkdir()
    for name, digest, extra in (("baseline", sha, {}), ("hybrid-rrf60", sha, {"hit6": 1.0, "mrr": 0.75}),
                                ("prefix", "0" * 64, {}), ("gemma", sha, {"self_graded": True})):
        (results / f"{name}.json").write_text(json.dumps(result(name, digest, **extra)), encoding="utf-8")
    experiments = tmp_path / "experiments.json"
    experiments.write_text(json.dumps({"experiments": [
        {"name": "baseline", "changes": {}, "takeaway": "The reference row."},
        {"name": "rerank-minilm-l6", "changes": {"retrieval": {"method": "rerank", "shortlist": 20,
                                                               "reranker": "cross-encoder/ms-marco-MiniLM-L6-v2",
                                                               "revision": "233902d25c44"}}},
        {"name": "hybrid-rrf60", "changes": {"retrieval": {"method": "hybrid", "shortlist": 20, "rrf_k": 60}},
         "takeaway": "Keywords help."},
        {"name": "prefix", "changes": {"embed_prefix": True}},
        {"name": "gemma", "changes": {"answer_model": "google/gemma-4-31b-it:free"}, "optional": True},
        {"name": "reasoning-low", "changes": {"reasoning_effort": "low"}, "optional": True},
    ]}), encoding="utf-8")
    return {"golden": golden, "results": results, "experiments": experiments, "tmp": tmp_path}


def build(files):
    return report.build_report(files["results"], files["experiments"], files["golden"])


def table_row(text, name):
    return next(line for line in text.splitlines() if line.startswith(f"| {name}"))


def test_one_row_per_experiment_from_its_result_file(files):
    text = build(files).table
    assert "| 0.500 |" in table_row(text, "baseline") and "| 1.000 |" in table_row(text, "hybrid-rrf60")
    assert "The reference row." in table_row(text, "baseline")


def test_unmeasured_answer_columns_read_not_measured(files):
    row = table_row(build(files).table, "baseline")
    assert row.count("not measured") == 2 and "| 0 |" in row


def test_a_row_without_a_takeaway_says_so(files):
    assert "no takeaway yet" in table_row(build(files).table, "prefix")


def test_a_row_from_another_golden_set_is_marked(files):
    assert "earlier golden set" in table_row(build(files).table, "prefix")
    assert "earlier golden set" not in table_row(build(files).table, "baseline")


def test_a_self_graded_row_is_marked(files):
    assert "self-graded" in table_row(build(files).table, "gemma")


def test_a_required_experiment_without_results_is_listed_as_not_run(files):
    assert "not run" in table_row(build(files).table, "rerank-minilm-l6")
    assert "reasoning-low" not in build(files).table  # optional and not run: left out


def test_the_change_is_described(files):
    text = build(files).table
    assert "MiniLM-L6-v2" in table_row(text, "rerank-minilm-l6") and "RRF" in table_row(text, "hybrid-rrf60")


def test_results_md_has_per_kind_figures_ranks_calibration_and_limits(files):
    md = build(files).markdown
    assert "## Per kind" in md and "## Evidence rank per question" in md
    assert "| s2 |" in md and "not measured (future work)" in md
    assert "3 questions" in md and "Questions drafted by Claude Code, reviewed by Nazeen Asif." in md


def test_the_readme_block_is_appended_then_replaced(files):
    readme = files["tmp"] / "README.md"
    readme.write_text("# Project\n\nIntro.\n", encoding="utf-8")
    built = build(files)
    report.update_readme(readme, built.readme_block)
    first = readme.read_text(encoding="utf-8")
    assert first.startswith("# Project\n\nIntro.\n") and report.START in first and report.END in first
    assert "Questions drafted by Claude Code, reviewed by Nazeen Asif." in first
    report.update_readme(readme, built.readme_block)
    assert readme.read_text(encoding="utf-8") == first
    readme.write_text(first.replace("Intro.", "Changed intro."), encoding="utf-8")
    report.update_readme(readme, built.readme_block)
    assert readme.read_text(encoding="utf-8").count(report.START) == 1


def test_the_command_writes_the_same_files_twice(files, capsys):
    from evaluation import __main__ as cli

    readme, out = files["tmp"] / "README.md", files["tmp"] / "results.md"
    readme.write_text("# P\n", encoding="utf-8")
    args = ["report", "--results", str(files["results"]), "--experiments", str(files["experiments"]),
            "--golden", str(files["golden"]), "--readme", str(readme), "--out", str(out)]
    assert cli.main(args) == 0
    first = (readme.read_text(encoding="utf-8"), out.read_text(encoding="utf-8"))
    assert cli.main(args) == 0
    assert (readme.read_text(encoding="utf-8"), out.read_text(encoding="utf-8")) == first
