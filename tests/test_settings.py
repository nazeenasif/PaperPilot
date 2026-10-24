"""Tests for paperpilot.config settings loading and validation."""

import dataclasses
from pathlib import Path

import pytest

from paperpilot import config
from paperpilot.config import Settings, load_settings
from paperpilot.errors import SettingsError

ENV_VARS = [
    "CHUNK_WORDS",
    "CHUNK_OVERLAP",
    "MIN_CHUNK_WORDS",
    "TOP_K",
    "LIBRARY_DIR",
    "EMBED_MODEL",
    "LLM_PROVIDER",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "RELEVANCE_THRESHOLD",
    "LLM_REASONING_EFFORT",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Remove settings env vars and stop a real .env file from being loaded."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "load_dotenv", lambda *args, **kwargs: False)


def test_defaults():
    s = load_settings()
    assert s.chunk_words == 220
    assert s.chunk_overlap == 40
    assert s.min_chunk_words == 30
    assert s.top_k == 6
    assert s.library_dir == Path("data/library")
    assert s.embed_model == "BAAI/bge-small-en-v1.5"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("CHUNK_WORDS", "300")
    monkeypatch.setenv("CHUNK_OVERLAP", "50")
    monkeypatch.setenv("MIN_CHUNK_WORDS", "20")
    monkeypatch.setenv("TOP_K", "10")
    monkeypatch.setenv("LIBRARY_DIR", "somewhere/else")
    monkeypatch.setenv("EMBED_MODEL", "other/model")
    s = load_settings()
    assert (s.chunk_words, s.chunk_overlap, s.min_chunk_words, s.top_k) == (300, 50, 20, 10)
    assert s.library_dir == Path("somewhere/else")
    assert s.embed_model == "other/model"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("CHUNK_WORDS", "abc"),
        ("TOP_K", "2.5"),
        ("CHUNK_WORDS", "0"),
        ("CHUNK_WORDS", "-5"),
        ("MIN_CHUNK_WORDS", "0"),
        ("TOP_K", "0"),
        ("CHUNK_OVERLAP", "-1"),
    ],
)
def test_invalid_number_names_variable_and_value(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(SettingsError) as exc:
        load_settings()
    assert name in str(exc.value)
    assert value in str(exc.value)


def test_overlap_must_be_less_than_chunk_words(monkeypatch):
    monkeypatch.setenv("CHUNK_OVERLAP", "220")
    with pytest.raises(SettingsError) as exc:
        load_settings()
    message = str(exc.value)
    assert "CHUNK_OVERLAP=220" in message
    assert "CHUNK_WORDS=220" in message


def test_min_chunk_words_must_be_less_than_chunk_words(monkeypatch):
    monkeypatch.setenv("MIN_CHUNK_WORDS", "300")
    with pytest.raises(SettingsError) as exc:
        load_settings()
    message = str(exc.value)
    assert "MIN_CHUNK_WORDS=300" in message
    assert "CHUNK_WORDS=220" in message


def test_empty_embed_model_rejected(monkeypatch):
    monkeypatch.setenv("EMBED_MODEL", "   ")
    with pytest.raises(SettingsError) as exc:
        load_settings()
    assert "EMBED_MODEL" in str(exc.value)


def test_settings_are_frozen():
    s = load_settings()
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.top_k = 99  # type: ignore[misc]


def test_describe_lists_every_field():
    text = load_settings().describe()
    for name in ENV_VARS:
        assert name in text


# --- LLM settings (Feature 2) ---

SECRET = "sk-or-v1-secret-test-value"


def test_llm_defaults():
    s = load_settings()
    assert s.llm_provider == "openrouter"
    assert s.llm_base_url == ""
    assert s.llm_api_key == ""
    assert s.llm_model == "nvidia/nemotron-3-ultra-550b-a55b:free"
    assert s.relevance_threshold == 0.60
    assert s.llm_reasoning_effort == ""


def test_llm_env_overrides(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_API_KEY", SECRET)
    monkeypatch.setenv("LLM_MODEL", "some/model")
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "0.5")
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
    s = load_settings()
    assert (s.llm_provider, s.llm_base_url, s.llm_model) == ("groq", "https://example.test/v1", "some/model")
    assert s.llm_api_key == SECRET
    assert s.relevance_threshold == 0.5
    assert s.llm_reasoning_effort == "low"


@pytest.mark.parametrize("value", ["abc", "-0.1", "1.5"])
def test_invalid_threshold_names_variable_and_value(monkeypatch, value):
    monkeypatch.setenv("RELEVANCE_THRESHOLD", value)
    with pytest.raises(SettingsError) as exc:
        load_settings()
    assert "RELEVANCE_THRESHOLD" in str(exc.value)
    assert value in str(exc.value)


@pytest.mark.parametrize("value", ["0", "1", "0.0", "1.0"])
def test_threshold_bounds_are_inclusive(monkeypatch, value):
    monkeypatch.setenv("RELEVANCE_THRESHOLD", value)
    assert load_settings().relevance_threshold == float(value)


def test_api_key_never_in_repr_or_describe(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", SECRET)
    s = load_settings()
    assert SECRET not in repr(s)
    text = s.describe()
    assert SECRET not in text
    assert "LLM_API_KEY = set (hidden)" in text


def test_describe_says_when_key_is_missing():
    assert "LLM_API_KEY = not set" in load_settings().describe()
