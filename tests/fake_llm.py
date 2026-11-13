"""A scripted fake of the OpenAI client for offline llm.py tests (not collected by pytest).

Responses and errors are built from the real openai types, constructed loosely the way the
SDK parses provider replies, so llm.py is tested against the same objects it sees in use.
openai 3.37.0 uses httpx2, so HTTP errors carry httpx2 requests and responses.
"""

import httpx2
import openai
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types.completion_usage import CompletionTokensDetails

URL = "https://openrouter.ai/api/v1/chat/completions"

_STATUS_ERRORS = {
    400: openai.BadRequestError,
    401: openai.AuthenticationError,
    403: openai.PermissionDeniedError,
    404: openai.NotFoundError,
    429: openai.RateLimitError,
}


def _completion(choices: list, usage, **extra) -> ChatCompletion:
    return ChatCompletion.construct(
        id="gen-test", object="chat.completion", created=0, model="test/model", choices=choices, usage=usage, **extra
    )


def ok(text: str, prompt_tokens: int = 10, completion_tokens: int = 20, reasoning_tokens: int | None = None):
    """A normal reply with usage counts."""
    message = ChatCompletionMessage.construct(role="assistant", content=text)
    details = CompletionTokensDetails.construct(reasoning_tokens=reasoning_tokens)
    usage = CompletionUsage.construct(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        completion_tokens_details=details,
    )
    return _completion([Choice.construct(index=0, finish_reason="stop", message=message)], usage)


def no_usage(text: str):
    """A normal reply whose provider sent no usage information."""
    message = ChatCompletionMessage.construct(role="assistant", content=text)
    return _completion([Choice.construct(index=0, finish_reason="stop", message=message)], None)


def length(reasoning_tokens: int = 2000):
    """Output cut off at the token limit after spending it on reasoning (empty content)."""
    message = ChatCompletionMessage.construct(role="assistant", content="")
    details = CompletionTokensDetails.construct(reasoning_tokens=reasoning_tokens)
    usage = CompletionUsage.construct(
        prompt_tokens=500, completion_tokens=reasoning_tokens, total_tokens=500 + reasoning_tokens,
        completion_tokens_details=details,
    )
    return _completion([Choice.construct(index=0, finish_reason="length", message=message)], usage)


def error_body(code: int, message: str = "provider error"):
    """An HTTP 200 reply that carries an error object and no choices (OpenRouter mid-request error)."""
    return _completion([], None, error={"code": code, "message": message})


def _response(code: int, headers: dict[str, str] | None = None) -> httpx2.Response:
    return httpx2.Response(code, headers=headers or {}, request=httpx2.Request("POST", URL))


def status_error(code: int, message: str = "error", headers: dict[str, str] | None = None) -> openai.APIStatusError:
    """A real openai status error (the right subclass for the code) with an httpx2 response."""
    cls = _STATUS_ERRORS.get(code, openai.InternalServerError if code >= 500 else openai.APIStatusError)
    body = {"error": {"code": code, "message": message}}
    return cls(message, response=_response(code, headers), body=body)


def rate_limited(retry_after: str | None = None, reset_ms: int | None = None) -> openai.RateLimitError:
    """A 429 with optional Retry-After (seconds) and X-RateLimit-Reset (epoch milliseconds) headers."""
    headers = {"X-RateLimit-Limit": "20", "X-RateLimit-Remaining": "0"}
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    if reset_ms is not None:
        headers["X-RateLimit-Reset"] = str(reset_ms)
    return status_error(429, "Rate limit exceeded", headers)


def timeout() -> openai.APITimeoutError:
    """A request that timed out."""
    return openai.APITimeoutError(request=httpx2.Request("POST", URL))


class _Completions:
    def __init__(self, client: "FakeClient") -> None:
        self._client = client

    def create(self, **kwargs):
        self._client.calls.append(kwargs)
        if not self._client.responses:
            raise AssertionError("FakeClient ran out of scripted responses")
        item = self._client.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class _Chat:
    def __init__(self, client: "FakeClient") -> None:
        self.completions = _Completions(client)


class _Model:
    def __init__(self, model_id: str) -> None:
        self.id = model_id


class _Models:
    def __init__(self, model_ids: list[str]) -> None:
        self._ids = model_ids

    def list(self):
        return [_Model(model_id) for model_id in self._ids]


class FakeClient:
    """Stands in for openai.OpenAI: returns or raises scripted items in order and records calls."""

    def __init__(self, responses: list, model_ids: list[str] | None = None) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []
        self.chat = _Chat(self)
        self.models = _Models(model_ids or [])
