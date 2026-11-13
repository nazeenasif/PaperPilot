"""API skeleton: readiness, localhost-only boundary, error kinds (contracts/web-api.md, ADR-0005)."""

import pytest

from conftest import wait_for_state

FRONTEND = "http://127.0.0.1:3000"


# --- readiness (research R9) ---


def test_status_reports_loading_then_ready(make_app, guarded):
    app, release = make_app(hold=True)
    with guarded(app) as client:
        assert client.get("/api/status").json()["state"] == "loading"
        release()
        body = wait_for_state(client, "ready")
    assert body["model"] == "test/model:free"
    assert body["model_is_free"] is True
    assert body["daily_limit"] == 50


def test_library_endpoints_are_not_ready_while_loading(make_app, guarded):
    app, release = make_app(hold=True)
    with guarded(app) as client:
        response = client.get("/api/papers")
        release()
    assert response.status_code == 503
    assert response.json() == {"kind": "not_ready", "state": "loading"}


def test_loader_failure_gives_error_state_without_details(make_app, guarded, api_env):
    def broken_loader():
        raise RuntimeError(f"model download failed with key {api_env['api_key']}")

    app, _ = make_app(loader=broken_loader)
    with guarded(app) as client:
        body = wait_for_state(client, "error")
        blocked = client.get("/api/papers")
    assert "RuntimeError" not in str(body) and "download" not in str(body)
    assert blocked.status_code == 503
    assert blocked.json() == {"kind": "not_ready", "state": "error"}


# --- localhost-only boundary (FR-002a, SC-012) ---


@pytest.mark.parametrize("origin", [FRONTEND, "http://localhost:3000"])
def test_cors_allows_both_frontend_origins(client, origin):
    allowed = client.options(
        "/api/status", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
    )
    assert allowed.headers.get("access-control-allow-origin") == origin
    assert client.get("/api/status", headers={"Origin": origin}).headers.get(
        "access-control-allow-origin"
    ) == origin


@pytest.mark.parametrize("origin", ["http://evil.example", "http://127.0.0.1:3001", "http://localhost:8080"])
def test_other_origins_are_refused(client, origin):
    preflight = client.options(
        "/api/status", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
    )
    assert preflight.status_code == 403
    assert "access-control-allow-origin" not in preflight.headers
    simple = client.get("/api/status", headers={"Origin": origin})
    assert simple.status_code == 403
    assert simple.json() == {"kind": "forbidden", "reason": "origin"}
    assert "access-control-allow-origin" not in simple.headers


def test_frontend_origins_come_from_settings(make_app, guarded, monkeypatch):
    monkeypatch.setenv("FRONTEND_ORIGINS", "http://127.0.0.1:3100")
    app, _ = make_app()
    with guarded(app) as client:
        allowed = client.get("/api/status", headers={"Origin": "http://127.0.0.1:3100"})
        refused = client.get("/api/status", headers={"Origin": FRONTEND})
    assert allowed.headers.get("access-control-allow-origin") == "http://127.0.0.1:3100"
    assert refused.status_code == 403


@pytest.mark.parametrize("host", ["192.168.1.20", "paperpilot.example", "0.0.0.0"])
def test_foreign_host_header_is_rejected(client, host):
    assert client.get("/api/status", headers={"Host": host}).status_code == 400


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.1:8000", "localhost:8000"])
def test_local_host_headers_are_accepted(client, host):
    assert client.get("/api/status", headers={"Host": host}).status_code == 200


def test_python_dash_m_api_binds_to_localhost(monkeypatch):
    import api.__main__ as entry

    calls = {}
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kwargs: calls.update(kwargs, app=app))
    entry.main()
    assert calls["host"] == "127.0.0.1"
    assert calls["port"] == 8000
    assert calls["app"] == "api.main:app"


# --- error contract (research R10) ---


def test_unexpected_error_is_internal_without_traceback(make_app, guarded, api_env):
    app, _ = make_app()

    @app.get("/api/boom")
    def boom():
        raise ValueError(f"database exploded near {api_env['api_key']}")

    with guarded(app, raise_server_exceptions=False) as client:
        wait_for_state(client, "ready")
        response = client.get("/api/boom")
    assert response.status_code == 500
    assert response.json() == {"kind": "internal"}
    assert "Traceback" not in response.text and "exploded" not in response.text


def test_unexpected_error_is_logged_to_api_log_with_the_key_scrubbed(make_app, guarded, api_env):
    app, _ = make_app()

    @app.get("/api/boom")
    def boom():
        raise ValueError(f"database exploded near {api_env['api_key']}")

    with guarded(app, raise_server_exceptions=False) as client:
        wait_for_state(client, "ready")
        client.get("/api/boom")
    log = (api_env["library_dir"] / "api.log").read_text(encoding="utf-8")
    assert "database exploded" in log
    assert api_env["api_key"] not in log


def test_unknown_api_path_is_a_json_404(client):
    response = client.get("/api/nothing-here")
    assert response.status_code == 404
    assert response.json() == {"kind": "not_found"}
