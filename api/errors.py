"""Error kinds sent to the browser (contracts/web-api.md, research R10).

Every error body is {"kind": ..., ...safe fields}. Messages, stack traces and provider text
never leave the server; the frontend owns all wording.
"""

import logging
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from paperpilot.errors import DailyLimitError, EmptyQueryError, LLMError, RateLimitedError, UnknownPassageError
from paperpilot.llm import MAX_ATTEMPTS

logger = logging.getLogger("api")

# kind -> HTTP status (contracts/web-api.md)
STATUS = {
    "forbidden": 403,
    "not_ready": 503,
    "empty_question": 422,
    "no_papers_selected": 422,
    "invalid_request": 422,
    "unknown_paper": 404,
    "unknown_passage": 404,
    "pdf_missing": 404,
    "not_found": 404,
    "not_saved": 404,
    "busy_question": 409,
    "busy_job": 409,
    "daily_limit": 429,
    "rate_limited": 429,
    "model_busy": 503,
    "model_unavailable": 502,
    "upload_invalid": 400,
    "internal": 500,
}


class ApiError(Exception):
    """An error to return to the browser as {"kind": kind, **fields}."""

    def __init__(self, kind: str, **fields: object) -> None:
        if kind not in STATUS:
            raise ValueError(f"Unknown error kind: {kind}")
        super().__init__(kind)
        self.kind = kind
        self.fields = fields

    @property
    def status(self) -> int:
        """HTTP status for this kind."""
        return STATUS[self.kind]

    def body(self) -> dict:
        """The JSON body sent to the browser."""
        return {"kind": self.kind, **self.fields}


# LLMError reasons that mean "the model is there but busy or slow" versus "it can't work as set up".
_BUSY_REASONS = {None, "busy", "timeout", "unreachable"}


def iso_utc(moment: datetime) -> str:
    """An aware datetime as ISO 8601 in UTC with a Z suffix."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def error_for(error: Exception) -> ApiError:
    """Map an engine exception to an error kind with safe fields; unexpected ones are logged."""
    if isinstance(error, ApiError):
        return error
    if isinstance(error, DailyLimitError):
        needed = {} if error.needed is None else {"needed": error.needed}
        return ApiError("daily_limit", used=error.used, limit=error.limit, resets_at=iso_utc(error.resets_at), **needed)
    if isinstance(error, RateLimitedError):
        return ApiError("rate_limited", until=iso_utc(error.until), daily=error.daily)
    if isinstance(error, LLMError):
        if error.reason in _BUSY_REASONS:
            return ApiError("model_busy", attempts=MAX_ATTEMPTS)  # every attempt was used
        return ApiError("model_unavailable", reason=error.reason)
    if isinstance(error, EmptyQueryError):
        return ApiError("empty_question")
    if isinstance(error, UnknownPassageError):
        return ApiError("unknown_passage")
    logger.error("Unexpected error", exc_info=error)
    return ApiError("internal")


def error_response(kind: str, **fields: object) -> JSONResponse:
    """A JSON error response for a kind."""
    error = ApiError(kind, **fields)
    return JSONResponse(error.body(), status_code=error.status)


def install_error_handlers(app: FastAPI) -> None:
    """Map every exception to a kind; unexpected ones are logged and reported as "internal"."""

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, error: ApiError) -> JSONResponse:
        return JSONResponse(error.body(), status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, error: RequestValidationError) -> JSONResponse:
        return error_response("invalid_request")

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, error: StarletteHTTPException) -> JSONResponse:
        if error.status_code == 404:
            return error_response("not_found")
        if error.status_code == 405:
            return JSONResponse({"kind": "invalid_request"}, status_code=405)
        logger.warning("HTTP %s on %s", error.status_code, request.url.path)
        return JSONResponse({"kind": "internal"}, status_code=error.status_code)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, error: Exception) -> JSONResponse:
        logger.error("Unexpected error on %s %s", request.method, request.url.path, exc_info=error)
        return error_response("internal")
