"""Shared exception hierarchy for PaperPilot."""


class PaperPilotError(Exception):
    """Base class for all user-facing PaperPilot errors."""


class SettingsError(PaperPilotError):
    """A setting is missing or invalid; the message names the variable and value."""


class PdfReadError(PaperPilotError):
    """The file is missing, not a PDF, corrupt, or cannot be opened."""


class NoTextError(PaperPilotError):
    """The PDF has no extractable text (for example, a scanned document)."""


class UnknownPaperError(PaperPilotError):
    """A paper ID is not in the library."""


class EmptyQueryError(PaperPilotError):
    """A search query is empty or whitespace only."""


class StorageError(PaperPilotError):
    """Writing to the library failed; any partial data has been removed."""
