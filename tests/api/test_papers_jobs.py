"""Library endpoints and upload jobs (contracts/web-api.md, data-model.md UploadJob, spec FR-016–FR-019).

Uploads are generated in the test (no committed PDFs). Every write sends X-PaperPilot: 1.
"""

import threading
import time

import pytest

from test_ask import HEADER, ask_stream, parse_sse

CARD_FIELDS = {
    "paper_id", "title", "page_count", "passage_count", "text_passages", "table_passages",
    "section_count", "arxiv_id", "has_pdf", "highlights",
}
JOB_FIELDS = {"job_id", "kind", "file_name", "phase", "percent", "outcome", "highlights", "paper_id", "error", "created_at"}
JOB_TIMEOUT = 20.0


def upload(client, *files: tuple[str, bytes]):
    return client.post(
        "/api/papers",
        files=[("files", (name, data, "application/pdf")) for name, data in files],
        headers=HEADER,
    )


def wait_for_jobs(client, count: int | None = None, timeout: float = JOB_TIMEOUT) -> list[dict]:
    """Poll GET /api/jobs until every job is ready or failed; return the snapshot."""
    deadline = time.monotonic() + timeout
    jobs: list[dict] = []
    while time.monotonic() < deadline:
        jobs = client.get("/api/jobs").json()["jobs"]
        if (count is None or len(jobs) >= count) and all(job["phase"] in ("ready", "failed") for job in jobs):
            return jobs
        time.sleep(0.02)
    raise AssertionError(f"jobs never finished: {jobs}")


def wait_for_phase(client, job_id: str, phase: str, timeout: float = JOB_TIMEOUT) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for job in client.get("/api/jobs").json()["jobs"]:
            if job["job_id"] == job_id and job["phase"] == phase:
                return job
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} never reached {phase}")


class EventRecorder:
    """Reads GET /api/jobs/events on a thread; stop() ends the stream through the registry."""

    def __init__(self, client) -> None:
        self.client = client
        self.jobs = client.app.state.jobs
        self.text = ""
        self.thread = threading.Thread(target=self._read, daemon=True)

    def _read(self) -> None:
        self.text = self.client.get("/api/jobs/events").text

    def __enter__(self) -> "EventRecorder":
        self.thread.start()
        deadline = time.monotonic() + JOB_TIMEOUT
        while self.jobs.subscriber_count() == 0:
            assert time.monotonic() < deadline, "the events stream never subscribed"
            time.sleep(0.01)
        return self

    def __exit__(self, *exc) -> None:
        self.jobs.close_streams()
        self.thread.join(timeout=JOB_TIMEOUT)

    def phases(self, job_id: str) -> list[str]:
        """The job's phases in order, with repeats (embedding percent updates) collapsed."""
        seen: list[str] = []
        for name, data in parse_sse(self.text):
            if name == "job" and data["job_id"] == job_id and (not seen or seen[-1] != data["phase"]):
                seen.append(data["phase"])
        return seen

    def order(self) -> list[tuple[str, str]]:
        return [(data["job_id"], data["phase"]) for name, data in parse_sse(self.text) if name == "job"]


@pytest.fixture
def pdf_bytes(tmp_path, make_pdf):
    """Return `build(name, title)` -> bytes of a generated paper (distinct titles, distinct content)."""

    def build(name: str = "paper.pdf", title: str = "A Study of Searching Research Papers by Meaning") -> bytes:
        return make_pdf(tmp_path / name, title=title).read_bytes()

    return build


# --- listing ---


def test_papers_lists_cards_with_every_field_and_the_total(client_with_paper):
    body = client_with_paper.get("/api/papers").json()
    assert set(body) == {"papers", "total_passages"}
    [card] = body["papers"]
    assert set(card) == CARD_FIELDS
    assert card["paper_id"] == client_with_paper.paper.paper_id
    assert card["has_pdf"] is True and card["highlights"] == "exact"
    assert body["total_passages"] == card["passage_count"] == client_with_paper.paper.passage_count


# --- uploading ---


def test_two_uploads_stream_their_phases_one_at_a_time(client, pdf_bytes):
    with EventRecorder(client) as events:
        response = upload(client, ("first.pdf", pdf_bytes("a.pdf", "First Paper")),
                          ("second.pdf", pdf_bytes("b.pdf", "Second Paper")))
        assert response.status_code == 202
        created = response.json()["jobs"]
        assert [job["file_name"] for job in created] == ["first.pdf", "second.pdf"]
        jobs = wait_for_jobs(client, 2)
    first, second = (job["job_id"] for job in created)
    for job_id in (first, second):
        assert events.phases(job_id) == ["queued", "parsing", "chunking", "embedding", "ready"]
    order = events.order()
    assert order.index((first, "ready")) < order.index((second, "parsing"))  # FIFO, one worker
    assert {job["outcome"] for job in jobs} == {"added"}
    assert all(set(job) == JOB_FIELDS for job in jobs)
    assert len(client.get("/api/papers").json()["papers"]) == 2


def test_embedding_reports_a_percent(client, pdf_bytes):
    with EventRecorder(client) as events:
        [job] = upload(client, ("paper.pdf", pdf_bytes())).json()["jobs"]
        wait_for_jobs(client, 1)
    percents = [data["percent"] for name, data in parse_sse(events.text)
                if name == "job" and data["job_id"] == job["job_id"] and data["phase"] == "embedding"]
    assert percents[0] == 0 and percents[-1] == 100


def test_jobs_snapshot_has_every_job(client, pdf_bytes):
    upload(client, ("paper.pdf", pdf_bytes()))
    [job] = wait_for_jobs(client, 1)
    assert job["kind"] == "upload" and job["phase"] == "ready" and job["outcome"] == "added"
    assert job["highlights"] == "exact" and job["paper_id"] and job["error"] is None


# --- duplicates and attach ---


def test_same_content_under_another_name_is_already_present(client_with_paper, tmp_path):
    data = (tmp_path / "paper.pdf").read_bytes()
    upload(client_with_paper, ("renamed copy.pdf", data))
    [job] = wait_for_jobs(client_with_paper, 1)
    assert (job["phase"], job["outcome"]) == ("ready", "already_present")
    assert job["paper_id"] == client_with_paper.paper.paper_id
    assert len(client_with_paper.get("/api/papers").json()["papers"]) == 1


def test_known_content_without_a_pdf_is_attached_and_mapped(client_with_paper, tmp_path, api_env):
    paper_id = client_with_paper.paper.paper_id
    pdfs = api_env["library_dir"] / "pdfs"
    (pdfs / f"{paper_id}.pdf").unlink()
    (pdfs / f"{paper_id}.layout.json").unlink()
    with EventRecorder(client_with_paper) as events:
        [created] = upload(client_with_paper, ("paper.pdf", (tmp_path / "paper.pdf").read_bytes())).json()["jobs"]
        [job] = wait_for_jobs(client_with_paper, 1)
    assert events.phases(created["job_id"]) == ["queued", "mapping", "ready"]
    assert (job["outcome"], job["highlights"]) == ("pdf_attached", "exact")
    [card] = client_with_paper.get("/api/papers").json()["papers"]
    assert card["has_pdf"] is True and card["highlights"] == "exact"


# --- rejected files ---


@pytest.mark.parametrize(
    ("name", "data", "reason"),
    [
        ("notes.pdf", b"just some text, not a PDF", "not_pdf"),
        ("broken.pdf", b"%PDF-1.7\nthis is not really a PDF\n", "unreadable"),
    ],
)
def test_rejected_bytes_create_a_failed_job(client, name, data, reason):
    response = upload(client, (name, data))
    assert response.status_code == 202
    [job] = wait_for_jobs(client, 1)
    assert (job["phase"], job["outcome"]) == ("failed", "failed")
    assert job["error"] == {"kind": "upload_invalid", "reason": reason}
    assert job["file_name"] == name


def test_a_file_over_the_limit_is_too_large(client, pdf_bytes, monkeypatch):
    from api import jobs

    monkeypatch.setattr(jobs, "MAX_UPLOAD_BYTES", 100)
    upload(client, ("big.pdf", pdf_bytes()))
    [job] = wait_for_jobs(client, 1)
    assert job["error"] == {"kind": "upload_invalid", "reason": "too_large"}
    assert client.get("/api/papers").json()["papers"] == []


def test_a_pdf_without_text_is_no_text(client, tmp_path, make_pdf):
    upload(client, ("blank.pdf", make_pdf(tmp_path / "blank.pdf", blank=True).read_bytes()))
    [job] = wait_for_jobs(client, 1)
    assert job["error"] == {"kind": "upload_invalid", "reason": "no_text"}


def test_every_dropped_file_gets_a_row(client, pdf_bytes):
    response = upload(client, ("good.pdf", pdf_bytes()), ("bad.txt", b"hello"))
    assert [job["file_name"] for job in response.json()["jobs"]] == ["good.pdf", "bad.txt"]
    jobs = {job["file_name"]: job for job in wait_for_jobs(client, 2)}
    assert jobs["good.pdf"]["outcome"] == "added"
    assert jobs["bad.txt"]["error"]["reason"] == "not_pdf"


def test_temporary_upload_files_are_removed(client, pdf_bytes, api_env):
    upload(client, ("paper.pdf", pdf_bytes()), ("bad.pdf", b"nope"))
    wait_for_jobs(client, 2)
    tmp = api_env["library_dir"] / "tmp"
    assert not tmp.exists() or list(tmp.rglob("*.pdf")) == []


def test_uploading_needs_the_header(client, pdf_bytes):
    response = client.post("/api/papers", files=[("files", ("paper.pdf", pdf_bytes(), "application/pdf"))])
    assert response.status_code == 403
    assert client.get("/api/jobs").json()["jobs"] == []


# --- re-processing ---


@pytest.fixture
def held_embedding(monkeypatch):
    """Make embedding wait until `release()`; `started` is set once a job is embedding."""
    from paperpilot import store

    started, gate = threading.Event(), threading.Event()
    fake = store.embed_passages  # the fake embedder, installed by api_env

    def embed_passages(texts, on_progress=None):
        started.set()
        assert gate.wait(JOB_TIMEOUT), "held embedding was never released"
        return fake(texts, on_progress)

    monkeypatch.setattr(store, "embed_passages", embed_passages)
    yield started, gate.set
    gate.set()


def test_reprocess_runs_to_reprocessed(client_with_paper):
    paper_id = client_with_paper.paper.paper_id
    with EventRecorder(client_with_paper) as events:
        response = client_with_paper.post(f"/api/papers/{paper_id}/reprocess", headers=HEADER)
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        assert response.json()["file_name"] == client_with_paper.paper.title
        [job] = wait_for_jobs(client_with_paper, 1)
    assert events.phases(job_id) == ["queued", "parsing", "chunking", "embedding", "ready"]
    assert (job["kind"], job["outcome"], job["highlights"]) == ("reprocess", "reprocessed", "exact")


def test_a_second_reprocess_while_one_is_queued_is_busy(client_with_paper, held_embedding):
    started, release = held_embedding
    paper_id = client_with_paper.paper.paper_id
    assert client_with_paper.post(f"/api/papers/{paper_id}/reprocess", headers=HEADER).status_code == 202
    assert started.wait(JOB_TIMEOUT)
    second = client_with_paper.post(f"/api/papers/{paper_id}/reprocess", headers=HEADER)
    assert second.status_code == 409
    assert second.json() == {"kind": "busy_job", "paper_id": paper_id}
    release()
    [job] = wait_for_jobs(client_with_paper, 1)
    assert job["outcome"] == "reprocessed"


@pytest.mark.parametrize(("setup", "kind"), [("unknown", "unknown_paper"), ("no_pdf", "pdf_missing")])
def test_reprocess_needs_a_known_paper_with_its_pdf(client_with_paper, api_env, setup, kind):
    paper_id = client_with_paper.paper.paper_id
    if setup == "unknown":
        paper_id = "000000000000"
    else:
        (api_env["library_dir"] / "pdfs" / f"{paper_id}.pdf").unlink()
    response = client_with_paper.post(f"/api/papers/{paper_id}/reprocess", headers=HEADER)
    assert response.status_code == 404
    assert response.json() == {"kind": kind, "paper_id": paper_id}


# --- deleting ---


def test_delete_removes_the_paper_and_reports_its_passages(client_with_paper, api_env):
    paper_id = client_with_paper.paper.paper_id
    response = client_with_paper.delete(f"/api/papers/{paper_id}", headers=HEADER)
    assert response.status_code == 200
    assert response.json() == {"removed_passages": client_with_paper.paper.passage_count}
    assert client_with_paper.get("/api/papers").json() == {"papers": [], "total_passages": 0}
    assert not (api_env["library_dir"] / "pdfs" / f"{paper_id}.pdf").exists()


def test_deleting_an_unknown_paper_is_404(client):
    response = client.delete("/api/papers/000000000000", headers=HEADER)
    assert response.status_code == 404
    assert response.json() == {"kind": "unknown_paper", "paper_id": "000000000000"}


# --- questions are not blocked by ingestion ---


def test_a_question_completes_while_a_job_is_embedding(client_with_paper, pdf_bytes, held_embedding, api_env):
    started, release = held_embedding
    upload(client_with_paper, ("new.pdf", pdf_bytes("new.pdf", "Another Paper")))
    assert started.wait(JOB_TIMEOUT)
    api_env["llm"].add("Evaluated on a benchmark dataset of questions [1].")
    status, _, events = ask_stream(client_with_paper, {"question": "Which evaluation dataset was used?"})
    assert status == 200 and events[-1][0] == "answer"
    assert client_with_paper.get("/api/jobs").json()["jobs"][0]["phase"] == "embedding"
    release()
    wait_for_jobs(client_with_paper, 1)
