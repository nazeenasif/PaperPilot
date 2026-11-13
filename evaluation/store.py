"""The evaluation cache, `<root>/data/eval/eval.sqlite3` (research R11, data-model.md).

It holds stored answers, claim verdicts and run progress. It contains passage text, so it lives
under the gitignored `data/` folder; committed results never read it. WAL with `BEGIN IMMEDIATE`
writes, as PaperPilot's other SQLite files (ADR-0007), so two processes never lose a write.
"""

import json
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

CACHE_FILE = Path("data") / "eval" / "eval.sqlite3"
NOT_JUDGED = "not_judged"

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS answers (config TEXT NOT NULL, question TEXT NOT NULL, run INTEGER NOT NULL, "
    "data TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (config, question, run))",
    "CREATE TABLE IF NOT EXISTS verdicts (key TEXT PRIMARY KEY, data TEXT NOT NULL, created_at TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS progress (experiment TEXT NOT NULL, stage TEXT NOT NULL, planned INTEGER NOT NULL "
    "DEFAULT 0, done INTEGER NOT NULL DEFAULT 0, requests_planned INTEGER NOT NULL DEFAULT 0, requests_retries "
    "INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (experiment, stage))",
    "CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, experiment TEXT NOT NULL, "
    "stage TEXT NOT NULL, started_at TEXT NOT NULL, slice INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0, "
    "ended_by TEXT)",
)
_prepared: set[Path] = set()
_prepare_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class EvalStore:
    """The cache under a project root (the repository root by default)."""

    def __init__(self, root: Path | str = ".") -> None:
        self.path = Path(root) / CACHE_FILE

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10.0, isolation_level=None)
        try:
            with _prepare_lock:
                if self.path not in _prepared:
                    for attempt in range(50):  # switching to WAL can report "locked" at once
                        try:
                            if db.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                                db.execute("PRAGMA journal_mode=WAL")
                            break
                        except sqlite3.OperationalError:
                            if attempt == 49:
                                raise
                            time.sleep(0.05)
                    for statement in _SCHEMA:
                        db.execute(statement)
                    _prepared.add(self.path)
        except BaseException:
            db.close()
            raise
        return db

    def _write(self, statements: list[tuple[str, tuple]]) -> None:
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            for sql, params in statements:
                db.execute(sql, params)
            db.execute("COMMIT")
        finally:
            db.close()

    def _read(self, sql: str, params: tuple) -> list[tuple]:
        db = self._connect()
        try:
            return db.execute(sql, params).fetchall()
        finally:
            db.close()

    # --- answers ---

    def save_answer(self, config: str, question: str, run: int, data: dict) -> None:
        """Store (or replace) an answer under its configuration hash, question id and run index."""
        self._write([("INSERT OR REPLACE INTO answers VALUES (?, ?, ?, ?, ?)",
                      (config, question, run, json.dumps(data), _now()))])

    def load_answer(self, config: str, question: str, run: int) -> dict | None:
        """The stored answer, or None."""
        rows = self._read("SELECT data FROM answers WHERE config = ? AND question = ? AND run = ?",
                          (config, question, run))
        return json.loads(rows[0][0]) if rows else None

    # --- verdicts ---

    def save_verdict(self, key: str, data: dict) -> None:
        """Store (or replace) a claim verdict under its key (research R7)."""
        self._write([("INSERT OR REPLACE INTO verdicts VALUES (?, ?, ?)", (key, json.dumps(data), _now()))])

    def load_verdict(self, key: str) -> dict | None:
        """The stored verdict, or None; a not-judged verdict is never final, so it reads as None."""
        rows = self._read("SELECT data FROM verdicts WHERE key = ?", (key,))
        if not rows:
            return None
        data = json.loads(rows[0][0])
        return None if data.get("verdict") == NOT_JUDGED else data

    # --- progress ---

    def _ensure(self, experiment: str, stage: str) -> tuple[str, tuple]:
        return ("INSERT OR IGNORE INTO progress (experiment, stage) VALUES (?, ?)", (experiment, stage))

    def set_planned(self, experiment: str, stage: str, planned: int) -> None:
        """Record how many units the stage needs in all."""
        self._write([self._ensure(experiment, stage),
                     ("UPDATE progress SET planned = ? WHERE experiment = ? AND stage = ?", (planned, experiment, stage))])

    def start_session(self, experiment: str, stage: str, slice_size: int) -> int:
        """Open a session with its slice; return its id."""
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute(*self._ensure(experiment, stage))
            cursor = db.execute("INSERT INTO sessions (experiment, stage, started_at, slice) VALUES (?, ?, ?, ?)",
                                (experiment, stage, _now(), slice_size))
            db.execute("COMMIT")
            return int(cursor.lastrowid)
        finally:
            db.close()

    def record_unit(self, experiment: str, stage: str, planned: int, retries: int, session: int | None = None) -> None:
        """Count one finished unit and the requests it used (first attempts and retries)."""
        statements = [self._ensure(experiment, stage),
                      ("UPDATE progress SET done = done + 1, requests_planned = requests_planned + ?, "
                       "requests_retries = requests_retries + ? WHERE experiment = ? AND stage = ?",
                       (planned, retries, experiment, stage))]
        if session is not None:
            statements.append(("UPDATE sessions SET used = used + ? WHERE id = ?", (planned + retries, session)))
        else:
            statements.append(("UPDATE sessions SET used = used + ? WHERE id = (SELECT MAX(id) FROM sessions WHERE "
                               "experiment = ? AND stage = ? AND ended_by IS NULL)",
                               (planned + retries, experiment, stage)))
        self._write(statements)

    def end_session(self, session: int, ended_by: str) -> None:
        """Close a session with why it ended: done, slice, daily_limit, rate_limited or busy."""
        self._write([("UPDATE sessions SET ended_by = ? WHERE id = ?", (ended_by, session))])

    def progress(self, experiment: str, stage: str) -> dict:
        """Planned and done units, the requests used and every session, for one stage of a run."""
        rows = self._read("SELECT planned, done, requests_planned, requests_retries FROM progress "
                          "WHERE experiment = ? AND stage = ?", (experiment, stage))
        planned, done, first, retries = rows[0] if rows else (0, 0, 0, 0)
        sessions = self._read("SELECT started_at, slice, used, ended_by FROM sessions WHERE experiment = ? "
                              "AND stage = ? ORDER BY id", (experiment, stage))
        return {
            "planned": planned,
            "done": done,
            "requests": {"planned": first, "retries": retries},
            "sessions": [{"started_at": s[0], "slice": s[1], "used": s[2], "ended_by": s[3]} for s in sessions],
        }
