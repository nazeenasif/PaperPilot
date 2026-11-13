"""Experiments and their configuration (research R11, data-model.md): what a row was measured with,
and the one-variable rule (FR-023). No model and no network."""

import json
import os

import pytest

from evaluation import experiments
from paperpilot import llm, prompts

GOLDEN = {"version": 1, "sha256": "abc"}


@pytest.fixture
def env(library_env, llm_env, monkeypatch):
    for name in ("EMBED_PREFIX", "SCOPE_RULE", "EVAL_JUDGE_MODEL", "USAGE_DIR"):
        monkeypatch.delenv(name, raising=False)
    return library_env


def test_the_configuration_records_every_field(env):
    config = experiments.configuration({}, paper_ids=[], golden=GOLDEN)
    assert set(config) == set(experiments.FIELDS)
    assert config["answer_model"] == "test/model:free"
    assert config["judge_model"] == "google/gemma-4-31b-it:free"
    assert config["output_tokens"] == llm.OUTPUT_TOKENS
    assert config["summary_prompt_version"] == prompts.SUMMARY_PROMPT_VERSION
    assert config["retrieval"] == experiments.BASELINE_RETRIEVAL
    assert (config["k"], config["chunk_words"], config["embed_prefix"], config["scope_rule"]) == (6, 220, False, True)
    assert config["golden"] == GOLDEN


def test_instruction_hashes_follow_the_instructions(env, monkeypatch):
    before = experiments.configuration({}, paper_ids=[], golden=GOLDEN)["instruction_hashes"]
    assert set(before) == {"answer", "rewrite", "section", "tldr", "row"}
    monkeypatch.setattr(prompts, "SYSTEM_INSTRUCTION", prompts.SYSTEM_INSTRUCTION + " Changed.")
    after = experiments.configuration({}, paper_ids=[], golden=GOLDEN)["instruction_hashes"]
    assert after["answer"] != before["answer"] and after["rewrite"] == before["rewrite"]


def test_changes_overlay_the_baseline(env):
    rerank = {"method": "rerank", "shortlist": 20, "reranker": "r", "revision": "abc"}
    config = experiments.configuration({"retrieval": rerank}, paper_ids=[], golden=GOLDEN)
    assert config["retrieval"] == rerank


def test_the_judge_never_grades_its_own_answers(env):
    config = experiments.configuration({"answer_model": "google/gemma-4-31b-it:free"}, paper_ids=[], golden=GOLDEN)
    assert config["judge_model"] == "nvidia/nemotron-3-ultra-550b-a55b:free"
    assert config["answer_model"] != config["judge_model"]


def test_the_answer_hash_ignores_what_does_not_change_an_answer(env):
    base = experiments.configuration({}, paper_ids=[], golden=GOLDEN)
    other_judge = {**base, "judge_model": "x/y:free", "golden": {"version": 2, "sha256": "d"}, "commit": "zzz"}
    assert experiments.answer_hash(base) == experiments.answer_hash(other_judge)
    assert experiments.answer_hash(base) != experiments.answer_hash({**base, "reasoning_effort": "low"})
    assert experiments.answer_hash(base) != experiments.answer_hash({**base, "retrieval": {"method": "hybrid"}})


def test_one_change_names_the_differences(env):
    base = experiments.configuration({}, paper_ids=[], golden=GOLDEN)
    assert experiments.differences(base, {**base, "reasoning_effort": "low"}) == ["reasoning_effort"]
    assert experiments.differences(base, {**base, "paper_fingerprints": {"a": "b"}, "commit": "z"}) == []
    assert experiments.differences(base, {**base, "answer_model": "g", "judge_model": "n"}) == ["answer_model"]


def test_two_changes_are_refused_with_their_names(env):
    base = experiments.configuration({}, paper_ids=[], golden=GOLDEN)
    with pytest.raises(ValueError, match="reasoning_effort.*scope_rule|scope_rule.*reasoning_effort"):
        experiments.check_one_change(base, {**base, "reasoning_effort": "low", "scope_rule": False})


def test_settings_for_maps_changes_to_environment_variables():
    assert experiments.environment_for({"answer_model": "g", "reasoning_effort": "low", "scope_rule": False,
                                        "embed_prefix": True}) == {
        "LLM_MODEL": "g", "LLM_REASONING_EFFORT": "low", "SCOPE_RULE": "false", "EMBED_PREFIX": "true",
    }
    assert experiments.environment_for({"retrieval": {"method": "hybrid"}}) == {}


def test_applied_sets_and_restores_the_environment(env, monkeypatch):
    monkeypatch.setenv("LLM_REASONING_EFFORT", "")
    with experiments.applied({"reasoning_effort": "low"}):
        assert os.environ["LLM_REASONING_EFFORT"] == "low"
    assert os.environ["LLM_REASONING_EFFORT"] == ""


def test_the_experiments_file_loads():
    loaded = experiments.load_experiments()
    names = [e.name for e in loaded]
    assert names[0] == "baseline" and len(names) == len(set(names)) == 9
    assert all(len(e.changes) <= 1 for e in loaded)


@pytest.mark.parametrize(
    "entry",
    [
        {"name": "two", "changes": {"reasoning_effort": "low", "scope_rule": False}},
        {"name": "unknown", "changes": {"colour": "blue"}},
        {"name": "bad-set", "changes": {}, "set": "elsewhere"},
        {"name": "bad-runs", "changes": {}, "runs": 0},
        {"changes": {}},
    ],
    ids=["two changes", "unknown setting", "unknown set", "no runs", "no name"],
)
def test_a_malformed_experiment_is_refused_with_its_name(tmp_path, entry):
    path = tmp_path / "experiments.json"
    path.write_text(json.dumps({"experiments": [{"name": "baseline", "changes": {}}, entry]}), encoding="utf-8")
    with pytest.raises(ValueError, match=entry.get("name", "experiment 2")):
        experiments.load_experiments(path)
