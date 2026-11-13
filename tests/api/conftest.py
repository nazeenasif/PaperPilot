"""Fixtures for the web API tests: the real FastAPI app over a temporary library, the fake
embedder and a scripted LLM. Nothing here can reach the model or the provider.

No __init__.py in tests/api: as a package it would be imported as "api" and shadow the real
api package under test."""

import threading
import time
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

BASE_URL = "http://127.0.0.1:8000"  # trusted hosts reject TestClient's default "testserver"
READY_TIMEOUT = 10.0


class GuardedClient(TestClient):
    """A TestClient that fails the test if any response body contains the API key."""

    def __init__(self, app, secret: str, **kwargs) -> None:
        super().__init__(app, **kwargs)
        self.secret = secret

    def request(self, *args, **kwargs):  # type: ignore[override]
        response = super().request(*args, **kwargs)
        assert self.secret not in response.text, "the API key appeared in a response"
        return response


@pytest.fixture
def api_env(library_env, fake_embedder, llm_env, fake_answers, monkeypatch):
    """Library, fake embedder, LLM settings and a scripted LLM, with the relevance gate off."""
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "0.0")
    return {"library_dir": library_env, "llm": fake_answers, "api_key": llm_env}


@pytest.fixture
def make_app(api_env) -> Callable:
    """Return `make(hold=False, loader=None)` -> (app, release). With hold=True the background
    loader waits until `release()` is called, so tests can observe the "loading" state."""

    def make(hold: bool = False, loader: Callable[[], None] | None = None):
        from api.main import create_app, default_loader

        gate = threading.Event()
        if not hold:
            gate.set()
        inner = loader or default_loader

        def gated_loader() -> None:
            if not gate.wait(timeout=READY_TIMEOUT):
                raise RuntimeError("test loader was never released")
            inner()

        return create_app(loader=gated_loader), gate.set

    return make


@pytest.fixture
def guarded(api_env) -> Callable[..., GuardedClient]:
    """Return `guarded(app)`: a GuardedClient for the app at the 127.0.0.1 base URL."""

    def build(app, **kwargs) -> GuardedClient:
        return GuardedClient(app, secret=api_env["api_key"], base_url=BASE_URL, **kwargs)

    return build


def wait_for_state(client: TestClient, wanted: str, timeout: float = READY_TIMEOUT) -> dict:
    """Poll /api/status until it reports `wanted`; return the last status body."""
    deadline = time.monotonic() + timeout
    body: dict = {}
    while time.monotonic() < deadline:
        body = client.get("/api/status").json()
        if body.get("state") == wanted:
            return body
        time.sleep(0.02)
    raise AssertionError(f"status never became {wanted!r}; last: {body}")


@pytest.fixture
def client(make_app, guarded) -> Iterator[GuardedClient]:
    """A ready app (lifespan running) over an empty temporary library."""
    app, _ = make_app()
    with guarded(app) as test_client:
        wait_for_state(test_client, "ready")
        yield test_client


@pytest.fixture
def client_with_paper(api_env, tmp_path, make_pdf, make_app, guarded) -> Iterator[GuardedClient]:
    """A ready app over a library holding one generated paper (added through the engine)."""
    from paperpilot.library import add_paper

    paper = add_paper(make_pdf(tmp_path / "paper.pdf"))
    app, _ = make_app()
    with guarded(app) as test_client:
        wait_for_state(test_client, "ready")
        test_client.paper = paper  # type: ignore[attr-defined]
        yield test_client
