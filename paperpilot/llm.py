"""The only module that talks to a language model (constitution Principles II and III, ADR-0003).

One OpenAI-compatible client is configured entirely by settings, so switching provider or
model needs no code. Retries follow the server's wait hints; cut-off output and persistent
failures become one readable LLMError line with the API key scrubbed out.
"""

import logging
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import openai

from paperpilot.config import Settings, load_settings
from paperpilot.errors import DailyLimitError, LLMError, RateLimitedError, SettingsError

logger = logging.getLogger(__name__)

DEFAULT_BASE_URLS = {"openrouter": "https://openrouter.ai/api/v1"}
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = (2.0, 4.0, 8.0)
MAX_WAIT_SECONDS = 60.0  # longer requested waits stop the call at once (FR-023a)
MAX_RESET_SECONDS = 48 * 3600  # an X-RateLimit-Reset further away is not trusted (FR-023b)
USAGE_FILE = "usage.sqlite3"
KEY_INFO_TIMEOUT_SECONDS = 10.0
# Reasoning tokens count against this limit, so it is generous for a ~150-word answer.
MAX_OUTPUT_TOKENS = 2048
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
_MAX_MESSAGE_CHARS = 300

_sleep = time.sleep  # replaced in tests
_planned = 0  # first attempts: one per generate() call
_retries = 0  # further attempts after a retryable failure
_clients: dict[tuple[str, str], object] = {}


@dataclass(frozen=True)
class RequestCounts:
    """Model requests since the last reset: first attempts (planned) and retries."""

    planned: int
    retries: int

    @property
    def total(self) -> int:
        """Every HTTP request sent, as the provider's rate limits count them."""
        return self.planned + self.retries

    def __sub__(self, other: "RequestCounts") -> "RequestCounts":
        return RequestCounts(self.planned - other.planned, self.retries - other.retries)


@dataclass(frozen=True)
class LLMReply:
    """A model reply with token counts (None when the provider does not report them)."""

    text: str
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    attempts: int
    seconds: float


@dataclass(frozen=True)
class RetryNotice:
    """Reported to `on_retry` before each retry wait (the web app's countdown, FR-023)."""

    attempt: int  # the attempt that failed, 1-based
    max_attempts: int
    wait_seconds: float
    reason: str  # "rate_limited", "timeout", "server_error" or "provider_error"


class ProviderError(Exception):
    """An error object that arrived inside an HTTP 200 response."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def request_count() -> int:
    """Return the number of HTTP requests sent to the model (including retries) since the last reset."""
    return _planned + _retries


def request_counts() -> RequestCounts:
    """Return first attempts and retries separately since the last reset."""
    return RequestCounts(planned=_planned, retries=_retries)


def reset_request_count() -> None:
    """Start counting model requests (first attempts and retries) from zero."""
    global _planned, _retries
    _planned = _retries = 0


# --- the shared daily request counter (FR-024–FR-026, ADR-0007) ---


@dataclass(frozen=True)
class Usage:
    """Today's model requests (UTC day): from PaperPilot's own count or the provider's figure."""

    used: int
    limit: int
    remaining: int
    resets_at: datetime
    source: str  # "local" or "provider"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _usage_connection(settings: Settings) -> sqlite3.Connection:
    """The usage database under LIBRARY_DIR; WAL and a busy timeout let the app and scripts share it."""
    settings.library_dir.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(Path(settings.library_dir) / USAGE_FILE, timeout=5.0, isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute(
        "CREATE TABLE IF NOT EXISTS daily_usage (day TEXT PRIMARY KEY, used INTEGER NOT NULL, "
        "request_limit INTEGER NOT NULL, source TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    return db


def _write_usage(sql: str, params: tuple, settings: Settings) -> None:
    """Run one write inside BEGIN IMMEDIATE, so concurrent writers never lose an update."""
    db = _usage_connection(settings)
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute(sql, params)
        db.execute("COMMIT")
    finally:
        db.close()


def count_request() -> None:
    """Add one model request (first attempt or retry) to today's shared count."""
    settings = load_settings()
    now = _utcnow()
    try:
        _write_usage(
            "INSERT INTO daily_usage (day, used, request_limit, source, updated_at) VALUES (?, 1, ?, 'local', ?) "
            "ON CONFLICT(day) DO UPDATE SET used = used + 1, updated_at = excluded.updated_at",
            (now.date().isoformat(), settings.daily_request_limit, now.isoformat()),
            settings,
        )
    except sqlite3.Error:
        logger.warning("Could not record a model request in %s", USAGE_FILE, exc_info=True)


def _record_provider_usage(used: int, limit: int, settings: Settings) -> None:
    now = _utcnow()
    _write_usage(
        "INSERT INTO daily_usage (day, used, request_limit, source, updated_at) VALUES (?, ?, ?, 'provider', ?) "
        "ON CONFLICT(day) DO UPDATE SET used = excluded.used, request_limit = excluded.request_limit, "
        "source = 'provider', updated_at = excluded.updated_at",
        (now.date().isoformat(), used, limit, now.isoformat()),
        settings,
    )


def usage() -> Usage:
    """Today's usage; resets at the next 00:00 UTC (the provider's day, research R7)."""
    settings = load_settings()
    now = _utcnow()
    resets_at = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    used, limit, source = 0, settings.daily_request_limit, "local"
    try:
        db = _usage_connection(settings)
        try:
            row = db.execute(
                "SELECT used, request_limit, source FROM daily_usage WHERE day = ?", (now.date().isoformat(),)
            ).fetchone()
        finally:
            db.close()
        if row:
            used, limit, source = row
    except sqlite3.Error:
        logger.warning("Could not read %s", USAGE_FILE, exc_info=True)
    return Usage(used, limit, max(limit - used, 0), resets_at, source)


def _fetch_key_info(settings: Settings) -> dict:
    """OpenRouter's GET /key data (free_model_daily_requests); not a model request."""
    response = httpx.get(
        f"{_base_url(settings)}/key",
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        timeout=KEY_INFO_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()["data"]


def refresh_usage() -> Usage:
    """Adopt the provider's own count of today's free requests when it can be read (OpenRouter only)."""
    settings = load_settings()
    if settings.llm_provider != "openrouter" or not settings.llm_api_key:
        return usage()
    try:
        counts = _fetch_key_info(settings)["free_model_daily_requests"]
        _record_provider_usage(int(counts["used"]), int(counts["limit"]), settings)
    except Exception as error:  # the local count stands
        logger.warning("Could not read the provider's request usage: %s", type(error).__name__)
    return usage()


def _base_url(settings: Settings) -> str:
    url = settings.llm_base_url or DEFAULT_BASE_URLS.get(settings.llm_provider, "")
    if not url:
        raise SettingsError(
            f"LLM_BASE_URL is not set and provider '{settings.llm_provider}' has no default; set LLM_BASE_URL"
        )
    return url


def _check_settings(settings: Settings) -> None:
    if not settings.llm_api_key:
        raise SettingsError("LLM_API_KEY is not set; add your provider's API key to .env")
    _base_url(settings)


def _build_client(settings: Settings) -> object:
    """Create an OpenAI-compatible client with the SDK's own retries switched off."""
    return openai.OpenAI(
        api_key=settings.llm_api_key,
        base_url=_base_url(settings),
        timeout=float(settings.llm_timeout_seconds),
        max_retries=0,
    )


def _make_client(settings: Settings) -> object:
    key = (settings.llm_api_key, _base_url(settings))
    if key not in _clients:
        _clients[key] = _build_client(settings)
    return _clients[key]


def _backoff(attempt: int) -> float:
    return BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS)) - 1]


def _headers(error: Exception):
    response = getattr(error, "response", None)
    return getattr(response, "headers", None) or {}


def _header_wait(headers, now: float, reset_allowed: bool = True) -> float | None:
    """Seconds the server asks us to wait (uncapped): Retry-After, else X-RateLimit-Reset.

    X-RateLimit-Reset is read as epoch milliseconds and trusted only if it resolves to a time
    in the future within 48 hours; anything else is ignored (FR-023b).
    """
    retry_after = headers.get("retry-after")
    if retry_after is not None:
        try:
            return max(float(retry_after), 0.0)
        except ValueError:
            pass  # an HTTP-date; fall through
    reset = headers.get("x-ratelimit-reset")
    if reset_allowed and reset is not None:
        try:
            seconds = int(reset) / 1000 - now
        except ValueError:
            return None
        if 0 < seconds <= MAX_RESET_SECONDS:
            return seconds
    return None


def requested_wait(error: Exception, now: float | None = None) -> float | None:
    """The wait the server asked for after this error, uncapped; None if it gave no usable hint."""
    now = time.time() if now is None else now
    if isinstance(error, (openai.APITimeoutError, openai.APIConnectionError)):
        return None
    return _header_wait(_headers(error), now, reset_allowed=getattr(error, "status_code", None) != 402)


def retry_wait(error: Exception, attempt: int, now: float | None = None) -> float | None:
    """Return seconds to wait before retrying after this error (at most 60), or None if it
    must not be retried."""
    now = time.time() if now is None else now
    if isinstance(error, (openai.APITimeoutError, openai.APIConnectionError)):
        return _backoff(attempt)
    status = getattr(error, "status_code", None)
    headers = _headers(error)
    if status == 402:  # out of credits: only a wait-and-retry case when the server says so
        hinted = _header_wait(headers, now, reset_allowed=False)
        return None if hinted is None else min(hinted, MAX_WAIT_SECONDS)
    if status not in RETRYABLE_STATUS:
        return None
    hinted = _header_wait(headers, now)
    return _backoff(attempt) if hinted is None else min(hinted, MAX_WAIT_SECONDS)


def _scrub(text: str, secret: str) -> str:
    return text.replace(secret, "***") if secret else text


def _one_line(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= _MAX_MESSAGE_CHARS else text[:_MAX_MESSAGE_CHARS] + "…"


def _failure_message(error: Exception, attempts: int, settings: Settings) -> str:
    label = settings.llm_provider
    detail = _one_line(getattr(error, "message", None) or error)
    status = getattr(error, "status_code", None)
    if status == 429:
        return (
            f"{label} rate limit: still limited after {attempts} attempts (free models allow 20 "
            f"requests/minute and 50/day without credits); try again later. Details: {detail}"
        )
    if status == 401:
        return f"{label} rejected the API key (check LLM_API_KEY). Details: {detail}"
    if status == 402:
        return f"{label} says the account is out of credits. Details: {detail}"
    if status == 404:
        return f"{label} does not know model '{settings.llm_model}' (check LLM_MODEL). Details: {detail}"
    if isinstance(error, openai.APITimeoutError):
        return (
            f"{label} did not answer within {settings.llm_timeout_seconds} s on {attempts} attempt(s); "
            "try again later or raise LLM_TIMEOUT_SECONDS."
        )
    if isinstance(error, openai.APIConnectionError):
        return f"Could not reach {label} after {attempts} attempt(s); check the network and LLM_BASE_URL."
    return f"{label} request failed (status {status}) after {attempts} attempt(s). Details: {detail}"


def _failure_reason(error: Exception) -> str:
    """Why a call failed for good, so the web app can pick a designed state (research R10)."""
    if isinstance(error, openai.APITimeoutError):
        return "timeout"
    if isinstance(error, openai.APIConnectionError):
        return "unreachable"
    status = getattr(error, "status_code", None)
    if status in (401, 403):
        return "bad_key"
    if status == 402:
        return "out_of_credits"
    if status == 404:
        return "unknown_model"
    if status in (400, 422):
        return "bad_request"
    return "busy"  # rate limits and server errors that outlasted every retry


def _is_daily_limit(error: Exception, settings: Settings) -> bool:
    """True if a 429 means today's free requests are used up, judged by its X-RateLimit-Limit
    header or, failing that, the provider's own remaining figure."""
    current = usage()
    limit_header = _headers(error).get("x-ratelimit-limit")
    if limit_header is not None and limit_header.strip() == str(current.limit):
        _record_provider_usage(current.limit, current.limit, settings)
        return True
    refreshed = refresh_usage()
    return refreshed.source == "provider" and refreshed.remaining <= 0


def _retry_reason(error: Exception) -> str:
    """A short reason for a retry log line: never the provider's message, the key or the prompt."""
    if isinstance(error, ProviderError):
        return f"error in a 200 response (code {error.status_code})"
    if isinstance(error, openai.APITimeoutError):
        return "timeout"
    if isinstance(error, openai.APIConnectionError):
        return "connection error"
    status = getattr(error, "status_code", None)
    if status == 429:
        return "rate limited (HTTP 429)"
    return f"HTTP {status}"


def _reset_note(error: Exception) -> str:
    """The raw X-RateLimit-Reset value for the retry log, so its units can be confirmed (FR-023b)."""
    raw = _headers(error).get("x-ratelimit-reset")
    return f" (X-RateLimit-Reset={raw})" if raw is not None else ""


def _notice_reason(error: Exception) -> str:
    """The reason category reported to on_retry (contracts/web-api.md, retry_wait event)."""
    if isinstance(error, ProviderError):
        return "provider_error"
    if isinstance(error, openai.APITimeoutError):
        return "timeout"
    if getattr(error, "status_code", None) == 429:
        return "rate_limited"
    return "server_error"


def _raise_for_error_body(response) -> None:
    """OpenRouter can report a failure inside an HTTP 200 body with no choices."""
    error = getattr(response, "error", None)
    if error:
        code = error.get("code") if isinstance(error, dict) else getattr(error, "code", None)
        message = error.get("message") if isinstance(error, dict) else getattr(error, "message", "")
        raise ProviderError(int(code or 502), str(message or "provider error"))
    if not getattr(response, "choices", None):
        raise ProviderError(502, "the provider returned no answer")


def _to_reply(response, attempts: int, seconds: float) -> LLMReply:
    choice = response.choices[0]
    text = choice.message.content or ""
    usage = getattr(response, "usage", None)
    details = getattr(usage, "completion_tokens_details", None) if usage else None
    reasoning = getattr(details, "reasoning_tokens", None) if details else None
    if choice.finish_reason == "length":
        raise LLMError(
            f"The model's output was cut off at {MAX_OUTPUT_TOKENS} tokens "
            f"({reasoning if reasoning is not None else 'unknown'} reasoning tokens used); "
            "set LLM_REASONING_EFFORT=low or choose another LLM_MODEL.",
            reason="cut_off",
        )
    if not text.strip():
        raise LLMError("The model returned an empty answer; try again or choose another LLM_MODEL.", reason="empty")
    return LLMReply(
        text=text,
        input_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
        output_tokens=getattr(usage, "completion_tokens", None) if usage else None,
        reasoning_tokens=reasoning,
        attempts=attempts,
        seconds=seconds,
    )


def model_is_listed() -> bool:
    """True if the provider's model list contains LLM_MODEL (not a chat request; not counted)."""
    settings = load_settings()
    _check_settings(settings)
    try:
        ids = {model.id for model in _make_client(settings).models.list()}
    except openai.APIError as error:
        message = _failure_message(error, 1, settings)
        raise LLMError(_scrub(message, settings.llm_api_key), reason=_failure_reason(error)) from None
    return settings.llm_model in ids


def generate(
    system: str, prompt: str, on_retry: Callable[[RetryNotice], None] | None = None
) -> LLMReply:
    """Send one system + user message to the configured model and return its reply.

    Raises SettingsError for missing settings and LLMError for provider failures, cut-off or
    empty output. Retries rate limits and transient errors (research R3); `on_retry`, if given,
    is told about each wait before it starts. Raises DailyLimitError, without sending anything,
    once today's requests are used up, and RateLimitedError at once when the provider asks for
    a wait longer than 60 s (ADR-0007). Every attempt is counted in the shared daily usage.
    """
    global _planned, _retries
    settings = load_settings()
    _check_settings(settings)
    today = usage()
    if today.used >= today.limit:
        raise DailyLimitError(today.used, today.limit, today.resets_at)
    client = _make_client(settings)
    kwargs: dict = {
        "model": settings.llm_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": MAX_OUTPUT_TOKENS,
    }
    if settings.llm_reasoning_effort:
        kwargs["extra_body"] = {"reasoning": {"effort": settings.llm_reasoning_effort}}

    start = time.perf_counter()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt == 1:
            _planned += 1
        else:
            _retries += 1
        count_request()
        try:
            response = client.chat.completions.create(**kwargs)
            _raise_for_error_body(response)
        except (openai.APIError, ProviderError) as error:
            requested = requested_wait(error)
            if requested is not None and requested > MAX_WAIT_SECONDS:
                daily = _is_daily_limit(error, settings)
                until = _utcnow() + timedelta(seconds=requested)
                logger.warning("LLM request attempt %d of %d failed: %s; asked to wait %.0f s, stopping%s",
                               attempt, MAX_ATTEMPTS, _retry_reason(error), requested, _reset_note(error))
                raise RateLimitedError(until, daily) from None
            wait = retry_wait(error, attempt)
            if wait is None or attempt == MAX_ATTEMPTS:
                message = _failure_message(error, attempt, settings)
                raise LLMError(_scrub(message, settings.llm_api_key), reason=_failure_reason(error)) from None
            logger.warning("LLM request attempt %d of %d failed: %s; retrying in %.1f s%s",
                           attempt, MAX_ATTEMPTS, _retry_reason(error), wait, _reset_note(error))
            if on_retry is not None:
                on_retry(RetryNotice(attempt, MAX_ATTEMPTS, wait, _notice_reason(error)))
            _sleep(wait)
            continue
        reply = _to_reply(response, attempt, time.perf_counter() - start)
        logger.info(
            "LLM reply: %d attempt(s), %.2f s, tokens in=%s out=%s reasoning=%s",
            reply.attempts, reply.seconds, reply.input_tokens, reply.output_tokens, reply.reasoning_tokens,
        )
        return reply
    raise AssertionError("unreachable")  # the loop always returns or raises
