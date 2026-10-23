"""Settings loaded from environment variables (and an optional .env file)."""

import os
from dataclasses import dataclass, fields
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
}


@dataclass(frozen=True)
class Settings:
    """Validated PaperPilot settings."""

    chunk_words: int = 220
    chunk_overlap: int = 40
    min_chunk_words: int = 30
    top_k: int = 6
    library_dir: Path = Path("data/library")
    embed_model: str = "BAAI/bge-small-en-v1.5"

    def describe(self) -> str:
        """Return one 'ENV_NAME = value' line per setting."""
        return "\n".join(
            f"{_ENV_NAMES[f.name]} = {getattr(self, f.name)}" for f in fields(self)
        )


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
    )
