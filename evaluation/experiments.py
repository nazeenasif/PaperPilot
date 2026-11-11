"""Experiments and the configuration a row is measured with (research R11, data-model.md).

An experiment changes exactly one setting from the baseline (FR-023). A retrieval method, with
its parameters, counts as one setting. The judge follows from the answering model, so that
neither grades itself (research R7), and is not counted as a change.
"""

import contextlib
import hashlib
import json
import os
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from paperpilot import library, llm, prompts
from paperpilot.config import Settings, load_settings

EXPERIMENTS_FILE = Path("eval") / "experiments.json"
BASELINE_RETRIEVAL = {"method": "vector", "shortlist": 20}

FIELDS = (
    "answer_model", "judge_model", "reasoning_effort", "output_tokens", "instruction_hashes",
    "summary_prompt_version", "judge_prompt_version", "chunk_words", "chunk_overlap", "min_chunk_words",
    "embed_model", "embed_prefix", "retrieval", "k", "relevance_threshold", "scope_rule",
    "paper_fingerprints", "golden", "commit",
)
# Follow from other settings (or record where the row came from), so they are not changes.
DERIVED = frozenset({"judge_model", "paper_fingerprints", "golden", "commit"})
# What can change an answer to a golden question.
ANSWER_FIELDS = (
    "answer_model", "reasoning_effort", "output_tokens", "instruction_hashes", "summary_prompt_version",
    "chunk_words", "chunk_overlap", "min_chunk_words", "embed_model", "embed_prefix", "retrieval", "k",
    "relevance_threshold", "scope_rule", "paper_fingerprints",
)
# Settings an experiment may change, and the environment variable that applies each one.
CHANGEABLE = {
    "answer_model": "LLM_MODEL",
    "reasoning_effort": "LLM_REASONING_EFFORT",
    "embed_prefix": "EMBED_PREFIX",
    "scope_rule": "SCOPE_RULE",
    "retrieval": None,  # applied by evaluation.retrieval, not through settings
}
SETS = ("golden", "scope_set")


@dataclass(frozen=True)
class Experiment:
    """One row of the results table: a name, at most one change, and the developer's takeaway."""

    name: str
    changes: dict = field(default_factory=dict)
    answers: bool = False
    optional: bool = False
    set: str = "golden"
    runs: int = 1
    takeaway: str | None = None


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def judge_for(answer_model: str, settings: Settings) -> str:
    """The judge for an answering model: EVAL_JUDGE_MODEL, or the default answering model when
    that is the one answering (research R7)."""
    if settings.eval_judge_model != answer_model:
        return settings.eval_judge_model
    return Settings().llm_model


def _commit() -> str:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def configuration(changes: dict, paper_ids: list[str], golden: dict, judge_prompt_version: int | None = None) -> dict:
    """Everything a row is measured with: today's settings with the experiment's changes on top."""
    settings = load_settings()
    config = {
        "answer_model": settings.llm_model,
        "reasoning_effort": settings.llm_reasoning_effort,
        "output_tokens": dict(llm.OUTPUT_TOKENS),
        "instruction_hashes": {
            "answer": _sha(prompts.SYSTEM_INSTRUCTION),
            "rewrite": _sha(prompts.REWRITE_INSTRUCTION),
            "section": _sha(prompts.SECTION_INSTRUCTION),
            "tldr": _sha(prompts.TLDR_INSTRUCTION),
            "row": _sha(prompts.ROW_INSTRUCTION),
        },
        "summary_prompt_version": prompts.SUMMARY_PROMPT_VERSION,
        "judge_prompt_version": judge_prompt_version,
        "chunk_words": settings.chunk_words,
        "chunk_overlap": settings.chunk_overlap,
        "min_chunk_words": settings.min_chunk_words,
        "embed_model": settings.embed_model,
        "embed_prefix": settings.embed_prefix,
        "retrieval": dict(BASELINE_RETRIEVAL),
        "k": settings.top_k,
        "relevance_threshold": settings.relevance_threshold,
        "scope_rule": settings.scope_rule,
        "paper_fingerprints": {pid: library.passage_fingerprint(pid) for pid in sorted(paper_ids)},
        "golden": dict(golden),
        "commit": _commit(),
    }
    config.update(changes)
    config["judge_model"] = judge_for(config["answer_model"], settings)
    return config


def answer_hash(config: dict) -> str:
    """A hash of the fields that can change an answer, so answers are reused only when all match."""
    return _sha(json.dumps({name: config.get(name) for name in ANSWER_FIELDS}, sort_keys=True))


def differences(base: dict, other: dict) -> list[str]:
    """The settings two configurations differ in, ignoring derived fields."""
    return sorted(name for name in FIELDS if name not in DERIVED and base.get(name) != other.get(name))


def check_one_change(base: dict, other: dict) -> None:
    """Raise ValueError, naming them, when two configurations differ in more than one setting."""
    changed = differences(base, other)
    if len(changed) > 1:
        raise ValueError(f"An experiment must change one setting from the baseline; this changes {', '.join(changed)}")


def environment_for(changes: dict) -> dict[str, str]:
    """The environment variables that apply an experiment's changes."""
    env = {}
    for name, value in changes.items():
        variable = CHANGEABLE.get(name)
        if variable:
            env[variable] = str(value).lower() if isinstance(value, bool) else str(value)
    return env


@contextlib.contextmanager
def applied(changes: dict) -> Iterator[None]:
    """Apply an experiment's changes to the environment for the duration of a run, then restore it."""
    env = environment_for(changes)
    saved = {name: os.environ.get(name) for name in env}
    os.environ.update(env)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def load_experiments(path: Path | str = EXPERIMENTS_FILE) -> list[Experiment]:
    """The experiments file, validated: unique names, at most one known change, a known set and
    at least one run. Raises ValueError naming the experiment."""
    entries = json.loads(Path(path).read_text(encoding="utf-8"))["experiments"]
    loaded: list[Experiment] = []
    for number, entry in enumerate(entries, start=1):
        name = entry.get("name") or f"experiment {number}"
        changes = entry.get("changes", {})
        problems = []
        if "name" not in entry:
            problems.append("it has no name")
        if not isinstance(changes, dict) or len(changes) > 1:
            problems.append("it must change at most one setting")
        elif set(changes) - set(CHANGEABLE):
            problems.append(f"unknown setting {sorted(set(changes) - set(CHANGEABLE))}")
        if entry.get("set", "golden") not in SETS:
            problems.append(f"unknown set {entry.get('set')!r}")
        if not isinstance(entry.get("runs", 1), int) or entry.get("runs", 1) < 1:
            problems.append("runs must be at least 1")
        if any(e.name == name for e in loaded):
            problems.append("the name is used twice")
        if problems:
            raise ValueError(f"{name}: {'; '.join(problems)}")
        loaded.append(Experiment(name=name, changes=changes, answers=bool(entry.get("answers", False)),
                                 optional=bool(entry.get("optional", False)), set=entry.get("set", "golden"),
                                 runs=entry.get("runs", 1), takeaway=entry.get("takeaway")))
    return loaded
