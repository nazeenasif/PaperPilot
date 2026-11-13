"""Process-wide API state: readiness of the engine and the one-question-at-a-time guard."""

import logging
import threading
import time
from collections.abc import Callable
from typing import Literal

from paperpilot import llm

logger = logging.getLogger("api")

State = Literal["loading", "ready", "error"]


class AppState:
    """Readiness of the model and library, set by the background loader (research R9)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: State = "loading"
        # Held while a question is being answered (FR-010); used by the ask endpoint.
        self.question_lock = threading.Lock()

    @property
    def state(self) -> State:
        """Current readiness: "loading", "ready" or "error"."""
        with self._lock:
            return self._state

    def run_loader(self, loader: Callable[[], None]) -> None:
        """Run the loader and record the outcome; failures are logged, never shown to clients."""
        try:
            loader()
        except Exception:
            logger.exception("Loading the model and library failed")
            self._set("error")
        else:
            logger.info("Model and library loaded; ready")
            self._set("ready")

    def _set(self, state: State) -> None:
        with self._lock:
            self._state = state


class UsageCache:
    """Today's usage for /api/usage and answers: the provider's figure at most every 30 s,
    the shared local count in between (ADR-0007)."""

    REFRESH_SECONDS = 30.0

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_refresh: float | None = None
        self.clock: Callable[[], float] = time.monotonic  # replaceable in tests

    def get(self) -> llm.Usage:
        with self._lock:
            now = self.clock()
            due = self._last_refresh is None or now - self._last_refresh >= self.REFRESH_SECONDS
            if due:
                self._last_refresh = now
        return llm.refresh_usage() if due else llm.usage()
