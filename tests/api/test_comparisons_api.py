"""Comparisons over HTTP (contracts/web-api.md Feature 4; spec US3). Scripted model only; every
write sends X-PaperPilot: 1."""

from collections.abc import Iterator

import pytest

from conftest import GuardedClient, wait_for_state
from paperpilot import library, llm
from test_ask import HEADER, parse_sse
from test_compare import RowLLM

ASPECTS = ["method", "datasets", "results"]


@pytest.fixture
def compare_client(api_env, summary_paper, second_paper, make_app, guarded, monkeypatch) -> Iterator[GuardedClient]:
    """A ready app over a library holding two papers, with a row-writing model."""
    first = library.add_paper(summary_paper)
    second = library.add_paper(second_paper)
    model = RowLLM()
    monkeypatch.setattr(llm, "generate", model)
    app, _ = make_app()
    with guarded(app) as client:
        wait_for_state(client, "ready")
        client.ids = [first.paper_id, second.paper_id]  # type: ignore[attr-defined]
        client.model = model  # type: ignore[attr-defined]
        yield client


def compare_stream(client, body: dict) -> tuple[int, str, list]:
    with client.stream("POST", "/api/comparisons", json=body, headers=HEADER) as response:
        text = "".join(response.iter_text())
    return response.status_code, text, parse_sse(text) if response.status_code == 200 else []


def test_a_comparison_streams_plan_progress_cells_then_the_comparison(compare_client):
    ids = compare_client.ids
    status, _, events = compare_stream(compare_client, {"paper_ids": ids, "aspects": ASPECTS})
    assert status == 200
    assert events[0] == ("plan", {"max_requests": 3, "parts": ASPECTS})
    assert {d["part"] for n, d in events if n == "progress"} == set(ASPECTS)
    cells = [d for n, d in events if n == "part"]
    assert len(cells) == 6 and cells[0]["part"] == f"method:{ids[0]}"
    name, comparison = events[-1]
    assert name == "comparison"
    assert comparison["paper_ids"] == ids and comparison["aspects"] == ASPECTS
    assert [p["label"] for p in comparison["papers"]] == ["P1", "P2"]
    assert (comparison["verified_cells"], comparison["total_cells"]) == (6, 6)
    assert comparison["requests"] == {"planned": 3, "retries": 0} and comparison["status"] == "current"
    assert {"model", "prompt_version", "created_at", "stale_reason", "passages", "rows"} <= set(comparison)


def test_a_cell_event_comes_only_after_its_row_was_generated(compare_client):
    _, _, events = compare_stream(compare_client, {"paper_ids": compare_client.ids, "aspects": ["method"]})
    names = [(n, d.get("step")) for n, d in events]
    assert names.index(("progress", "generating")) < names.index(("part", None))


def test_a_malformed_row_sends_row_failed_and_the_rest_runs(compare_client):
    compare_client.model.overrides = {"Method": "not json"}
    _, _, events = compare_stream(compare_client, {"paper_ids": compare_client.ids, "aspects": ["method", "results"]})
    assert ("row_failed", {"aspect": "method", "reason": "malformed"}) in events
    rows = events[-1][1]["rows"]
    assert (rows[0]["state"], rows[0]["cells"]) == ("failed", []) and rows[1]["state"] == "ok"


@pytest.mark.parametrize(
    "shape",
    [
        lambda a, b: {"paper_ids": [a], "aspects": ASPECTS},
        lambda a, b: {"paper_ids": [a, b, "c", "d", "e"], "aspects": ASPECTS},
        lambda a, b: {"paper_ids": [a, a], "aspects": ASPECTS},
        lambda a, b: {"paper_ids": [a, b], "aspects": []},
        lambda a, b: {"paper_ids": [a, b], "aspects": ["poetry"]},
        lambda a, b: {"paper_ids": [a, b], "aspects": ASPECTS, "retry_aspects": []},
        lambda a, b: {"paper_ids": [a, b], "aspects": ["method"], "retry_aspects": ["results"]},
    ],
    ids=["one paper", "five papers", "duplicates", "no aspects", "unknown aspect", "empty retry", "retry outside"],
)
def test_invalid_requests_are_refused_before_the_stream(compare_client, shape):
    response = compare_client.post("/api/comparisons", json=shape(*compare_client.ids), headers=HEADER)
    assert response.status_code == 422 and response.json()["kind"] == "invalid_request"
    assert compare_client.model.calls == []


def test_an_unknown_paper_is_404(compare_client):
    body = {"paper_ids": [compare_client.ids[0], "000000000000"], "aspects": ASPECTS}
    response = compare_client.post("/api/comparisons", json=body, headers=HEADER)
    assert response.status_code == 404 and response.json()["kind"] == "unknown_paper"


def test_a_write_without_the_header_is_refused(compare_client):
    response = compare_client.post("/api/comparisons", json={"paper_ids": compare_client.ids, "aspects": ASPECTS})
    assert response.status_code == 403 and compare_client.model.calls == []


def test_get_finds_a_saved_comparison_in_any_order(compare_client):
    a, b = compare_client.ids
    compare_stream(compare_client, {"paper_ids": [a, b], "aspects": ["method", "results"]})
    calls = len(compare_client.model.calls)
    found = compare_client.get(f"/api/comparisons?papers={b},{a}&aspects=results,method")
    assert found.status_code == 200 and found.json()["status"] == "current"
    assert found.json()["plan"] == {"max_requests": 2, "parts": ["method", "results"]}
    assert len(compare_client.model.calls) == calls


def test_get_with_nothing_saved_is_not_saved_with_the_plan(compare_client):
    a, b = compare_client.ids
    response = compare_client.get(f"/api/comparisons?papers={a},{b}&aspects=method")
    assert response.status_code == 404
    assert response.json() == {"kind": "not_saved", "plan": {"max_requests": 1, "parts": ["method"]}}


def test_get_with_bad_input_is_refused(compare_client):
    a, _ = compare_client.ids
    assert compare_client.get(f"/api/comparisons?papers={a}&aspects=method").status_code == 422
    assert compare_client.get(f"/api/comparisons?papers={a},000000000000&aspects=method").status_code == 404


def test_a_second_post_reopens_with_no_request(compare_client):
    body = {"paper_ids": compare_client.ids, "aspects": ["method"]}
    compare_stream(compare_client, body)
    calls = len(compare_client.model.calls)
    status, _, events = compare_stream(compare_client, body)
    assert status == 200 and events[-1][0] == "comparison" and len(compare_client.model.calls) == calls


def test_retry_aspects_reruns_one_row(compare_client):
    compare_client.model.overrides = {"Results": "not json"}
    body = {"paper_ids": compare_client.ids, "aspects": ["method", "results"]}
    compare_stream(compare_client, body)
    compare_client.model.overrides = {}
    calls = len(compare_client.model.calls)
    _, _, events = compare_stream(compare_client, {**body, "retry_aspects": ["results"]})
    assert events[0] == ("plan", {"max_requests": 1, "parts": ["results"]})
    assert len(compare_client.model.calls) == calls + 1 and events[-1][1]["rows"][1]["state"] == "ok"


def test_retrying_with_nothing_saved_is_not_saved(compare_client):
    body = {"paper_ids": compare_client.ids, "aspects": ["method"], "retry_aspects": ["method"]}
    response = compare_client.post("/api/comparisons", json=body, headers=HEADER)
    assert response.status_code == 404 and response.json()["kind"] == "not_saved"


def test_retrying_an_earlier_comparison_is_refused(compare_client):
    body = {"paper_ids": compare_client.ids, "aspects": ["method"]}
    compare_stream(compare_client, body)
    library.reprocess_paper(compare_client.ids[0])
    response = compare_client.post("/api/comparisons", json={**body, "retry_aspects": ["method"]}, headers=HEADER)
    assert response.status_code == 422
    a, b = compare_client.ids
    saved = compare_client.get(f"/api/comparisons?papers={a},{b}&aspects=method").json()
    assert (saved["status"], saved["stale_reason"]) == ("stale", "passages_changed")
