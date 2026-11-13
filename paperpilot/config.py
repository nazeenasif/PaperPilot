"""Settings loaded from environment variables (and an optional .env file)."""

import os
from dataclasses import dataclass, field, fields
from pathlib import Path

from dotenv import load_dotenv

from paperpilot.errors import SettingsError

# Maps each Settings field to its environment variable.
_ENV_NAMES = {
    "chunk_words": "CHUNK_WORDS",
    "chunk_overlap": "CHUNK_OVERLAP",
    "min_chunk_words": "MIN_CHUNK_WORDS",
    "top_k": "TOP_K",
    "library_dir": "LIBRARY_DIR",
    "embed_model": "EMBED_MODEL",
    "llm_provider": "LLM_PROVIDER",
    "llm_base_url": "LLM_BASE_URL",
    "llm_api_key": "LLM_API_KEY",
    "llm_model": "LLM_MODEL",
    "relevance_threshold": "RELEVANCE_THRESHOLD",
    "llm_reasoning_effort": "LLM_REASONING_EFFORT",
    "llm_timeout_seconds": "LLM_TIMEOUT_SECONDS",
    "daily_request_limit": "DAILY_REQUEST_LIMIT",
    "frontend_origins": "FRONTEND_ORIGINS",
    "usage_dir": "USAGE_DIR",
    "embed_prefix": "EMBED_PREFIX",
    "scope_rule": "SCOPE_RULE",
    "eval_judge_model": "EVAL_JUDGE_MODEL",
    "eval_reserve": "EVAL_RESERVE",
}
# Settings whose values must never be printed.
_SECRET_FIELDS = {"llm_api_key"}


@dataclass(frozen=True)
class Settings:
    """Validated PaperPilot settings."""

    chunk_words: int = 220
    chunk_overlap: int = 40
    min_chunk_words: int = 30
    top_k: int = 6
    library_dir: Path = Path("data/library")
    embed_model: str = "BAAI/bge-small-en-v1.5"
    llm_provider: str = "openrouter"
    llm_base_url: str = ""  # empty: the provider's default (see llm.DEFAULT_BASE_URLS)
    llm_api_key: str = field(default="", repr=False)
    llm_model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    relevance_threshold: float = 0.58  # calibrated for bge-small on the test library (research R8)
    llm_reasoning_effort: str = ""  # empty: the model's default
    llm_timeout_seconds: int = 60  # per model request (research R13)
    daily_request_limit: int = 50  # free requests per UTC day; the provider's figure wins when known
    # Browser origins the web API accepts (CORS and the Origin guard, research R11).
    frontend_origins: tuple[str, ...] = ("http://127.0.0.1:3000", "http://localhost:3000")
    # Feature 5, the evaluation harness (contracts/engine-api.md); each default is today's behaviour.
    usage_dir: Path | None = None  # where usage.sqlite3 lives; None: LIBRARY_DIR
    embed_prefix: bool = False  # embed "title. section. text"; the stored text is unchanged
    scope_rule: bool = True  # the scope rule in the section, TL;DR and row instructions
    eval_judge_model: str = "google/gemma-4-31b-it:free"  # the harness's judge
    eval_reserve: int = 10  # requests an evaluation session never spends

    def describe(self) -> str:
        """Return one 'ENV_NAME = value' line per setting; secrets show only whether they are set."""
        lines = []
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name in _SECRET_FIELDS:
                value = "set (hidden)" if value else "not set"
            elif isinstance(value, tuple):
                value = ",".join(value)
            lines.append(f"{_ENV_NAMES[f.name]} = {value}")
        return "\n".join(lines)


def _read_int(name: str, default: int, minimum: int) -> int:
    """Read an integer env var, requiring value >= minimum."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        raise SettingsError(f"{name}={raw} is not a whole number") from None
    if value < minimum:
        raise SettingsError(f"{name}={raw} must be at least {minimum}")
    return value


def _read_fraction(name: str, default: float) -> float:
    """Read a number between 0 and 1 (inclusive) from an env var."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw.strip())
    except ValueError:
        raise SettingsError(f"{name}={raw} is not a number") from None
    if not 0.0 <= value <= 1.0:
        raise SettingsError(f"{name}={raw} must be between 0 and 1")
    return value


def _read_text(name: str, default: str) -> str:
    """Read a text env var; empty or missing gives the default."""
    return (os.getenv(name) or "").strip() or default


_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _read_bool(name: str, default: bool) -> bool:
    """Read an on/off env var (1/0, true/false, yes/no, on/off, any case)."""
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    raise SettingsError(f"{name}={raw} is not on or off; use true or false")


def _read_list(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """Read a comma-separated env var; blank entries are ignored, at least one is required."""
    raw = os.getenv(name)
    if raw is None:
        return default
    items = tuple(item.strip() for item in raw.split(",") if item.strip())
    if not items:
        raise SettingsError(f"{name}={raw} lists no values; give at least one or remove the variable")
    return items


def load_settings() -> Settings:
    """Load settings from .env and the environment, validating every value."""
    load_dotenv()
    defaults = Settings()

    chunk_words = _read_int("CHUNK_WORDS", defaults.chunk_words, 1)
    chunk_overlap = _read_int("CHUNK_OVERLAP", defaults.chunk_overlap, 0)
    min_chunk_words = _read_int("MIN_CHUNK_WORDS", defaults.min_chunk_words, 1)
    top_k = _read_int("TOP_K", defaults.top_k, 1)

    if chunk_overlap >= chunk_words:
        raise SettingsError(
            f"CHUNK_OVERLAP={chunk_overlap} must be less than CHUNK_WORDS={chunk_words}"
        )
    if min_chunk_words >= chunk_words:
        raise SettingsError(
            f"MIN_CHUNK_WORDS={min_chunk_words} must be less than CHUNK_WORDS={chunk_words}"
        )

    library_dir = Path(os.getenv("LIBRARY_DIR") or defaults.library_dir)
    embed_model = os.getenv("EMBED_MODEL", defaults.embed_model).strip()
    if not embed_model:
        raise SettingsError("EMBED_MODEL is empty; set a model name or remove the variable")

    return Settings(
        chunk_words=chunk_words,
        chunk_overlap=chunk_overlap,
        min_chunk_words=min_chunk_words,
        top_k=top_k,
        library_dir=library_dir,
        embed_model=embed_model,
        llm_provider=_read_text("LLM_PROVIDER", defaults.llm_provider).lower(),
        llm_base_url=_read_text("LLM_BASE_URL", defaults.llm_base_url),
        llm_api_key=_read_text("LLM_API_KEY", defaults.llm_api_key),
        llm_model=_read_text("LLM_MODEL", defaults.llm_model),
        relevance_threshold=_read_fraction("RELEVANCE_THRESHOLD", defaults.relevance_threshold),
        llm_reasoning_effort=_read_text("LLM_REASONING_EFFORT", defaults.llm_reasoning_effort),
        llm_timeout_seconds=_read_int("LLM_TIMEOUT_SECONDS", defaults.llm_timeout_seconds, 1),
        daily_request_limit=_read_int("DAILY_REQUEST_LIMIT", defaults.daily_request_limit, 1),
        frontend_origins=_read_list("FRONTEND_ORIGINS", defaults.frontend_origins),
        usage_dir=Path(os.getenv("USAGE_DIR")) if (os.getenv("USAGE_DIR") or "").strip() else library_dir,
        embed_prefix=_read_bool("EMBED_PREFIX", defaults.embed_prefix),
        scope_rule=_read_bool("SCOPE_RULE", defaults.scope_rule),
        eval_judge_model=_read_text("EVAL_JUDGE_MODEL", defaults.eval_judge_model),
        eval_reserve=_read_int("EVAL_RESERVE", defaults.eval_reserve, 0),
    )
