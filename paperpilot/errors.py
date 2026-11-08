"""Shared exception hierarchy for PaperPilot."""

from datetime import datetime

# Why a model call failed, so callers (the web API) can choose a designed state without
# parsing messages (research R10).
LLM_ERROR_REASONS = frozenset(
    {
        "busy",
        "not_listed",
        "unknown_model",
        "bad_key",
        "out_of_credits",
        "cut_off",
        "empty",
        "timeout",
        "unreachable",
        "bad_request",
        "daily_limit",
        "rate_limited",
    }
)


class PaperPilotError(Exception):
    """Base class for all user-facing PaperPilot errors."""


class SettingsError(PaperPilotError):
    """A setting is missing or invalid; the message names the variable and value."""


class PdfReadError(PaperPilotError):
    """The file is missing, not a PDF, corrupt, or cannot be opened."""


class PasswordProtectedError(PdfReadError):
    """The PDF is encrypted and needs a password to open."""


class NoTextError(PaperPilotError):
    """The PDF has no extractable text (for example, a scanned document)."""


class UnknownPaperError(PaperPilotError):
    """A paper ID is not in the library."""


class UnknownPassageError(PaperPilotError):
    """A passage ID is not in the library."""


class EmptyQueryError(PaperPilotError):
    """A search query is empty or whitespace only."""


class StorageError(PaperPilotError):
    """Writing to the library failed; any partial data has been removed."""


class RowFormatError(PaperPilotError):
    """A comparison row's reply is not the expected JSON; a per-row failure, never shown raw."""


class LLMError(PaperPilotError):
    """The language model failed; the message is one readable line with no secrets. `tokens` holds
    the provider's counts when it charged for output, as a cut-off does."""

    def __init__(self, message: str, reason: str | None = None, tokens: dict[str, int] | None = None) -> None:
        if reason is not None and reason not in LLM_ERROR_REASONS:
            raise ValueError(f"Unknown LLMError reason: {reason}")
        super().__init__(message)
        self.reason = reason
        self.tokens = tokens


class DailyLimitError(LLMError):
    """Today's free model requests are used up; no request was sent."""

    def __init__(self, used: int, limit: int, resets_at: datetime) -> None:
        super().__init__(
            f"Daily model request limit reached ({used} of {limit}); resets at {resets_at.isoformat()}",
            reason="daily_limit",
        )
        self.used = used
        self.limit = limit
        self.resets_at = resets_at


class RateLimitedError(LLMError):
    """The provider asked for a wait longer than the retry cap; the call stopped at once."""

    def __init__(self, until: datetime, daily: bool = False) -> None:
        super().__init__(f"rate limited until {until.isoformat()}", reason="rate_limited")
        self.until = until
        self.daily = daily


class PdfMissingError(PaperPilotError):
    """The paper is in the library but its PDF copy is not stored."""

    def __init__(self, paper_id: str) -> None:
        super().__init__(f"Paper {paper_id} has no stored PDF; add its file again to attach it")
        self.paper_id = paper_id
