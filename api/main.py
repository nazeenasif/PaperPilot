"""The FastAPI application: lifespan, background loading, boundary middleware and logging.

Run with `python -m api` (or `uvicorn api.main:app --host 127.0.0.1 --port 8000`).
"""

import logging
import threading
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from api.errors import error_response, install_error_handlers
from api.routes import router
from api.security import HEADER_NAME, OriginGuard
from api.state import AppState
from paperpilot import library, llm, store
from paperpilot.config import Settings, load_settings

logger = logging.getLogger("api")

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]  # defence against DNS rebinding (research R11)
LOG_FILE = "api.log"


def default_loader() -> None:
    """Load the embedding model, open the library with a warm-up search and refresh usage."""
    store.load_model()
    library.search("warm up")
    refresh = getattr(llm, "refresh_usage", None)  # added with request accounting (ADR-0007)
    if refresh is not None:
        try:
            refresh()
        except Exception:
            logger.warning("Could not refresh request usage at startup", exc_info=True)


class ScrubbingFormatter(logging.Formatter):
    """Formats log records (tracebacks included) and replaces the API key with ***."""

    def __init__(self, secret: str) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s: %(message)s")
        self.secret = secret

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        return text.replace(self.secret, "***") if self.secret else text


def _open_log(settings: Settings) -> logging.Handler:
    """Log the api and paperpilot loggers to <LIBRARY_DIR>/api.log, key scrubbed."""
    settings.library_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(settings.library_dir / LOG_FILE, encoding="utf-8")
    handler.setFormatter(ScrubbingFormatter(settings.llm_api_key))
    handler.setLevel(logging.INFO)
    for name in ("api", "paperpilot"):
        target = logging.getLogger(name)
        target.addHandler(handler)
        if target.level == logging.NOTSET or target.level > logging.INFO:
            target.setLevel(logging.INFO)
    return handler


def _close_log(handler: logging.Handler) -> None:
    for name in ("api", "paperpilot"):
        logging.getLogger(name).removeHandler(handler)
    handler.close()


def create_app(loader: Callable[[], None] | None = None) -> FastAPI:
    """Build the API. The loader runs in a background thread so /api/status answers at once."""
    settings = load_settings()
    app_state = AppState()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        handler = _open_log(settings)
        thread = threading.Thread(
            target=app_state.run_loader, args=(loader or default_loader,), name="paperpilot-loader", daemon=True
        )
        thread.start()
        try:
            yield
        finally:
            _close_log(handler)

    app = FastAPI(title="PaperPilot API", lifespan=lifespan)
    app.state.settings = settings
    app.state.paperpilot = app_state

    @app.middleware("http")
    async def require_ready(request: Request, call_next):
        """Every /api path except /api/status needs the model and library (research R9)."""
        path = request.url.path
        if path.startswith("/api/") and path != "/api/status" and app_state.state != "ready":
            return error_response("not_ready", state=app_state.state)
        return await call_next(request)

    # Added last = runs first: trusted hosts, then the Origin guard, then CORS, then readiness.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.frontend_origins),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", HEADER_NAME],
        allow_credentials=False,
    )
    app.add_middleware(OriginGuard, allowed_origins=settings.frontend_origins)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

    install_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
