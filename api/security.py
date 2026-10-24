"""Cross-site request protection (spec FR-002b, research R11, ADR-0005).

CORS only stops a foreign page from reading responses; browsers still send "simple" cross-site
requests (form-style POSTs, multipart uploads). Before any endpoint runs, this middleware:

1. refuses a request whose Origin header is present and not an allowed frontend origin;
2. refuses a state-changing request without `X-PaperPilot: 1`. A custom header makes the request
   non-simple, so a browser must first send a CORS preflight, which only allowed origins pass.

Same-machine scripts send no Origin and only need the header to change state.
"""

from collections.abc import Iterable

from starlette.types import ASGIApp, Receive, Scope, Send

from api.errors import error_response

HEADER_NAME = "X-PaperPilot"
HEADER_VALUE = "1"
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class OriginGuard:
    """ASGI middleware enforcing the two rules above; placed inside trusted hosts, outside CORS."""

    def __init__(self, app: ASGIApp, allowed_origins: Iterable[str]) -> None:
        self.app = app
        self.allowed_origins = frozenset(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {name.lower(): value for name, value in scope["headers"]}
        origin = headers.get(b"origin")
        if origin is not None and origin.decode("latin-1") not in self.allowed_origins:
            await error_response("forbidden", reason="origin")(scope, receive, send)
            return
        if scope["method"] in WRITE_METHODS and headers.get(HEADER_NAME.lower().encode()) != HEADER_VALUE.encode():
            await error_response("forbidden", reason="header")(scope, receive, send)
            return
        await self.app(scope, receive, send)
