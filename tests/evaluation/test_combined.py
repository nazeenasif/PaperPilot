"""A combined row: an experiment built on another row (`base`) still changes exactly one setting,
counted from that row (FR-023), and the report says so and shows the overall conclusion.
A fixture library with the fake embedder; no model, no network."""

import json

import pytest

from evaluation import experiments, golden, report, retrieval
from evaluation.experiments import Experiment

HYBRID = {"method": "hybrid", "shortlist": 20, "rrf_k": 60, "bm25": {"k1": 1.5, "b": 0.75}}


def write(tmp_path, entries, **extra):
    path = tmp_path / "experiments.json"
    path.write_text(json.dumps({"experiments": entries, **extra}), encoding="utf-8")
    return path


def test_a_based_experiment_loads_with_its_base(tmp_path):
    loaded = experiments.load_experiments(write(tmp_path, [
        {"name": "prefix", "changes": {"embed_prefix": True}},
        {"name": "prefix-hybrid", "base": "prefix", "changes": {"retrieval": HYBRID}}]))
    assert loaded[1].base == "prefix"
    assert experiments.resolved_changes(loaded[1], {e.name: e for e in loaded}) == \
        {"embed_prefix": True, "retrieval": HYBRID}


@pytest.mark.parametrize("entries", [
    [{"name": "x", "base": "missing", "changes": {}}],
    [{"name": "a", "base": "b", "changes": {}}, {"name": "b", "changes": {}}],  # base must come first
    [{"name": "p", "changes": {"embed_prefix": True}}, {"name": "q", "base": "p", "changes": {"embed_prefix": False}},
     {"name": "r", "base": "q", "changes": {"retrieval": HYBRID}}],  # no chains
])
def test_a_bad_base_is_refused(tmp_path, entries):
    with pytest.raises(ValueError):
        experiments.load_experiments(write(tmp_path, entries))


def _golden(tmp_path):
    arxiv = "2401.00001"
    path = tmp_path / "golden.json"
    path.write_text(json.dumps({"version": 1, "papers": [arxiv], "questions": [
        {"id": "s1", "kind": "single", "question": "Which corpus?", "scope": "library", "papers": [arxiv],
         "expected": "Abstracts.", "evidence": [{"paper": arxiv, "page": 1, "phrase": "large corpus of abstracts"}]}]}),
        encoding="utf-8")
    return golden.load_golden(path)


def test_a_combined_row_runs_with_both_changes(eval_paper, tmp_path, monkeypatch):
    used = []
    monkeypatch.setattr(retrieval, "experiment_library", lambda e: _record(used, e))
    loaded = _golden(tmp_path)
    base = Experiment("prefix", changes={"embed_prefix": True})
    combined = Experiment("prefix-hybrid", changes={"retrieval": HYBRID}, base="prefix")
    result = retrieval.run_experiment(combined, loaded, retrieval.baseline_configuration(loaded), base=base)
    assert used == [{"embed_prefix": True, "retrieval": HYBRID}]
    assert result["base"] == "prefix"
    assert result["configuration"]["embed_prefix"] is True
    assert result["configuration"]["retrieval"]["method"] == "hybrid"


def _record(used, experiment):
    import contextlib

    used.append(experiment.changes)
    return contextlib.nullcontext()


def test_the_report_names_the_base_and_shows_the_conclusion(tmp_path):
    golden_file = tmp_path / "golden.json"
    golden_file.write_text(json.dumps({"version": 1, "papers": [], "questions": []}), encoding="utf-8")
    experiments_file = write(tmp_path, [
        {"name": "prefix", "changes": {"embed_prefix": True}},
        {"name": "prefix-hybrid", "base": "prefix", "changes": {"retrieval": HYBRID}}],
        conclusion="The prefix helps most.")
    results = tmp_path / "results"
    results.mkdir()
    built = report.build_report(results, experiments_file, golden_file)
    row = next(line for line in built.table.splitlines() if line.startswith("| prefix-hybrid"))
    assert "prefix + BM25" in row
    assert "The prefix helps most." in built.readme_block.split(report.HEADER)[0]
    assert "The prefix helps most." in built.markdown.split(report.HEADER)[0]
