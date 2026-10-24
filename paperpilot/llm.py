"""The only module that talks to a language model (constitution Principles II and III, ADR-0003).

One OpenAI-compatible client is configured entirely by settings, so switching provider or
model needs no code. Retries follow the server's wait hints; cut-off output and persistent
failures become one readable LLMError line with the API key scrubbed out.
"""

import logging
import time
from dataclasses import dataclass

import openai

from paperpilot.config import Settings, load_settings
from paperpilot.errors import LLMError, SettingsError

logger = logging.getLogger(__name__)

DEFAULT_BASE_URLS = {"openrouter": "https://openrouter.ai/api/v1"}
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = (2.0, 4.0, 8.0)
MAX_WAIT_SECONDS = 60.0
TIMEOUT_SECONDS = 60.0
# Reasoning tokens count against this limit, so it is generous for a ~150-word answer.
MAX_OUTPUT_TOKENS = 2048
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
_MAX_MESSAGE_CHARS = 300

_sleep = time.sleep  # replaced in tests
_requests = 0
_clients: dict[tuple[str, str], object] = {}


@dataclass(frozen=True)
class LLMReply:
    """A model reply with token counts (None when the provider does not report them)."""

    text: str
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    attempts: int
    seconds: float


class ProviderError(Exception):
    """An error object that arrived inside an HTTP 200 response."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def request_count() -> int:
    """Return the number of HTTP requests sent to the model (including retries) since the last reset."""
    return _requests


def reset_request_count() -> None:
    """Start counting model requests from zero."""
    global _requests
    _requests = 0


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
        timeout=TIMEOUT_SECONDS,
        max_retries=0,
    )


def _make_client(settings: Settings) -> object:
    key = (settings.llm_api_key, _base_url(settings))
    if key not in _clients:
        _clients[key] = _build_client(settings)
    return _clients[key]


def _backoff(attempt: int) -> float:
    return BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS)) - 1]


def _header_wait(headers, now: float, reset_allowed: bool = True) -> float | None:
    """Seconds to wait from Retry-After, else from X-RateLimit-Reset (epoch ms); None if absent."""
    retry_after = headers.get("retry-after")
    if retry_after is not None:
        try:
            return min(max(float(retry_after), 0.0), MAX_WAIT_SECONDS)
        except ValueError:
            pass  # an HTTP-date; fall through
    reset = headers.get("x-ratelimit-reset")
    if reset_allowed and reset is not None:
        try:
            return min(max(int(reset) / 1000 - now, 0.0), MAX_WAIT_SECONDS)
        except ValueError:
            pass
    return None


def retry_wait(error: Exception, attempt: int, now: float | None = None) -> float | None:
    """Return seconds to wait before retrying after this error, or None if it must not be retried."""
    now = time.time() if now is None else now
    if isinstance(error, (openai.APITimeoutError, openai.APIConnectionError)):
        return _backoff(attempt)
    status = getattr(error, "status_code", None)
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None) or {}
    if status == 402:  # out of credits: only a wait-and-retry case when the server says so
        return _header_wait(headers, now, reset_allowed=False)
    if status not in RETRYABLE_STATUS:
        return None
    hinted = _header_wait(headers, now)
    return _backoff(attempt) if hinted is None else hinted


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
    if isinstance(error, (openai.APITimeoutError, openai.APIConnectionError)):
        return f"Could not reach {label} after {attempts} attempt(s) ({type(error).__name__})."
    return f"{label} request failed (status {status}) after {attempts} attempt(s). Details: {detail}"


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
            "set LLM_REASONING_EFFORT=low or choose another LLM_MODEL."
        )
    if not text.strip():
        raise LLMError("The model returned an empty answer; try again or choose another LLM_MODEL.")
    return LLMReply(
        text=text,
        input_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
        output_tokens=getattr(usage, "completion_tokens", None) if usage else None,
        reasoning_tokens=reasoning,
        attempts=attempts,
        seconds=seconds,
    )


def generate(system: str, prompt: str) -> LLMReply:
    """Send one system + user message to the configured model and return its reply.

    Raises SettingsError for missing settings and LLMError for provider failures, cut-off or
    empty output. Retries rate limits and transient errors (research R3).
    """
    global _requests
    settings = load_settings()
    _check_settings(settings)
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
        _requests += 1
        try:
            response = client.chat.completions.create(**kwargs)
            _raise_for_error_body(response)
        except (openai.APIError, ProviderError) as error:
            wait = retry_wait(error, attempt)
            if wait is None or attempt == MAX_ATTEMPTS:
                message = _failure_message(error, attempt, settings)
                raise LLMError(_scrub(message, settings.llm_api_key)) from None
            logger.info("LLM request %d failed (status %s); retrying in %.1f s", attempt,
                        getattr(error, "status_code", "-"), wait)
            _sleep(wait)
            continue
        reply = _to_reply(response, attempt, time.perf_counter() - start)
        logger.info(
            "LLM reply: %d attempt(s), %.2f s, tokens in=%s out=%s reasoning=%s",
            reply.attempts, reply.seconds, reply.input_tokens, reply.output_tokens, reply.reasoning_tokens,
        )
        return reply
    raise AssertionError("unreachable")  # the loop always returns or raises
