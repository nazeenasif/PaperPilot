"""Cross-site request protection (spec FR-002b, research R11, analysis finding A1).

CORS only stops a foreign page from reading responses; browsers still send "simple" requests.
The API must refuse foreign origins and writes without X-PaperPilot: 1 before any endpoint runs.
"""

import pytest

from conftest import wait_for_state

ALLOWED = ["http://127.0.0.1:3000", "http://localhost:3000"]
FOREIGN = "http://evil.example"
HEADER = {"X-PaperPilot": "1"}


@pytest.fixture
def echo_client(make_app, guarded):
    """A ready app with test-only routes that record whether they ran."""
    app, _ = make_app()
    ran: list[str] = []

    @app.post("/api/echo")
    def echo_post():
        ran.append("post")
        return {"ok": True}

    @app.delete("/api/echo")
    def echo_delete():
        ran.append("delete")
        return {"ok": True}

    @app.get("/api/echo")
    def echo_get():
        ran.append("get")
        return {"ok": True}

    with guarded(app) as client:
        wait_for_state(client, "ready")
        client.ran = ran  # type: ignore[attr-defined]
        yield client


# --- rule 1: a present Origin must be an allowed frontend origin ---


def test_cross_origin_simple_post_is_refused_before_the_endpoint_runs(echo_client):
    response = echo_client.post(
        "/api/echo",
        content="anything",
        headers={"Origin": FOREIGN, "Content-Type": "text/plain"},
    )
    assert response.status_code == 403
    assert response.json() == {"kind": "forbidden", "reason": "origin"}
    assert echo_client.ran == []


def test_cross_origin_multipart_upload_is_refused(echo_client):
    response = echo_client.post(
        "/api/echo",
        files={"files": ("paper.pdf", b"%PDF-1.7 fake", "application/pdf")},
        headers={"Origin": FOREIGN},
    )
    assert response.status_code == 403
    assert response.json()["reason"] == "origin"
    assert echo_client.ran == []


def test_cross_origin_write_is_refused_even_with_the_header(echo_client):
    response = echo_client.post("/api/echo", headers={"Origin": FOREIGN, **HEADER})
    assert response.status_code == 403
    assert response.json()["reason"] == "origin"
    assert echo_client.ran == []


def test_cross_origin_read_is_refused(echo_client):
    response = echo_client.get("/api/echo", headers={"Origin": FOREIGN})
    assert response.status_code == 403
    assert echo_client.ran == []


def test_cross_origin_preflight_is_refused(echo_client):
    response = echo_client.options(
        "/api/echo",
        headers={
            "Origin": FOREIGN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-paperpilot",
        },
    )
    assert response.status_code == 403
    assert "access-control-allow-origin" not in response.headers


# --- rule 2: state-changing requests need X-PaperPilot: 1 ---


@pytest.mark.parametrize("origin", [*ALLOWED, None])
def test_write_without_the_header_is_refused(echo_client, origin):
    headers = {"Origin": origin} if origin else {}
    post = echo_client.post("/api/echo", json={"a": 1}, headers=headers)
    delete = echo_client.delete("/api/echo", headers=headers)
    for response in (post, delete):
        assert response.status_code == 403
        assert response.json() == {"kind": "forbidden", "reason": "header"}
    assert echo_client.ran == []


def test_write_with_a_wrong_header_value_is_refused(echo_client):
    response = echo_client.post("/api/echo", headers={"Origin": ALLOWED[0], "X-PaperPilot": "yes"})
    assert response.status_code == 403
    assert response.json()["reason"] == "header"


@pytest.mark.parametrize("origin", ALLOWED)
def test_write_with_the_header_from_an_allowed_origin_runs(echo_client, origin):
    response = echo_client.post("/api/echo", json={"a": 1}, headers={"Origin": origin, **HEADER})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert echo_client.ran == ["post"]


@pytest.mark.parametrize("origin", ALLOWED)
def test_preflight_for_the_header_from_an_allowed_origin_is_allowed(echo_client, origin):
    response = echo_client.options(
        "/api/echo",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-paperpilot",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert "x-paperpilot" in response.headers.get("access-control-allow-headers", "").lower()


def test_same_machine_scripts_without_origin_can_read_and_write_with_the_header(echo_client):
    assert echo_client.get("/api/echo").status_code == 200
    assert echo_client.post("/api/echo", headers=HEADER).status_code == 200
    assert echo_client.delete("/api/echo", headers=HEADER).status_code == 200
    assert echo_client.ran == ["get", "post", "delete"]


def test_status_is_also_protected_from_foreign_origins(echo_client):
    assert echo_client.get("/api/status", headers={"Origin": FOREIGN}).status_code == 403
    assert echo_client.get("/api/status").status_code == 200
