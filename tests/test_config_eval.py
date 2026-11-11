"""Settings added for the evaluation harness (Feature 5, contracts/engine-api.md). Each defaults
to today's behaviour. No model and no network."""

import pytest

from paperpilot import llm
from paperpilot.config import load_settings
from paperpilot.errors import SettingsError

NAMES = ["USAGE_DIR", "EMBED_PREFIX", "SCOPE_RULE", "EVAL_JUDGE_MODEL", "EVAL_RESERVE"]


@pytest.fixture
def clean_env(library_env, monkeypatch):
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)
    return library_env


def test_defaults_keep_todays_behaviour(clean_env):
    settings = load_settings()
    assert settings.usage_dir == settings.library_dir
    assert settings.embed_prefix is False
    assert settings.scope_rule is True
    assert settings.eval_judge_model == "google/gemma-4-31b-it:free"
    assert settings.eval_reserve == 10


def test_values_are_read(clean_env, monkeypatch, tmp_path):
    monkeypatch.setenv("USAGE_DIR", str(tmp_path / "usage"))
    monkeypatch.setenv("EMBED_PREFIX", "true")
    monkeypatch.setenv("SCOPE_RULE", "off")
    monkeypatch.setenv("EVAL_JUDGE_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
    monkeypatch.setenv("EVAL_RESERVE", "0")
    settings = load_settings()
    assert settings.usage_dir == tmp_path / "usage"
    assert (settings.embed_prefix, settings.scope_rule) == (True, False)
    assert settings.eval_judge_model == "nvidia/nemotron-3-ultra-550b-a55b:free"
    assert settings.eval_reserve == 0


@pytest.mark.parametrize(("raw", "value"), [("1", True), ("yes", True), ("ON", True), ("0", False), ("no", False), ("False", False)])
def test_switches_accept_common_words(clean_env, monkeypatch, raw, value):
    monkeypatch.setenv("EMBED_PREFIX", raw)
    assert load_settings().embed_prefix is value


@pytest.mark.parametrize(("name", "raw"), [("EMBED_PREFIX", "maybe"), ("SCOPE_RULE", "2"), ("EVAL_RESERVE", "-1"), ("EVAL_RESERVE", "ten")])
def test_bad_values_are_refused(clean_env, monkeypatch, name, raw):
    monkeypatch.setenv(name, raw)
    with pytest.raises(SettingsError, match=name):
        load_settings()


def test_describe_lists_the_new_settings(clean_env):
    text = load_settings().describe()
    assert all(f"{name} = " in text for name in NAMES)


def test_usage_is_counted_under_usage_dir(clean_env, monkeypatch, tmp_path, llm_env):
    shared = tmp_path / "shared"
    monkeypatch.setenv("USAGE_DIR", str(shared))
    llm.count_request()
    assert (shared / llm.USAGE_FILE).exists()
    assert not (clean_env / llm.USAGE_FILE).exists()
    assert llm.usage().used == 1


def test_usage_stays_under_the_library_by_default(clean_env, llm_env):
    llm.count_request()
    assert (clean_env / llm.USAGE_FILE).exists()
