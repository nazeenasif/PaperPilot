"""HTTP endpoints (contracts/web-api.md). Each one calls the engine and maps the result."""

from collections.abc import AsyncIterable
from dataclasses import asdict

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent

from api.errors import ApiError, error_for
from api.schemas import AskIn, StatusOut, answer_body
from api.streams import run_streaming
from paperpilot import library, llm, service, store
from paperpilot.config import Settings
from paperpilot.errors import PdfMissingError, UnknownPaperError, UnknownPassageError
from paperpilot.service import Turn

router = APIRouter(prefix="/api")


@router.get("/status", response_model=StatusOut)
def get_status(request: Request) -> StatusOut:
    """Readiness and the configured model; answers while loading (research R9)."""
    settings: Settings = request.app.state.settings
    return StatusOut(
        state=request.app.state.paperpilot.state,
        model=settings.llm_model,
        model_is_free=settings.llm_model.endswith(":free"),
        daily_limit=settings.daily_request_limit,
    )


def start_question(body: AskIn, request: Request) -> AskIn:
    """Validate before the stream starts (plain JSON errors) and take the one-question lock."""
    if not body.question.strip():
        raise ApiError("empty_question")
    if body.paper_ids is not None:
        if not body.paper_ids:
            raise ApiError("no_papers_selected")
        for paper_id in body.paper_ids:
            if not store.has_paper(paper_id):
                raise ApiError("unknown_paper", paper_id=paper_id)
    if not request.app.state.paperpilot.question_lock.acquire(blocking=False):
        raise ApiError("busy_question")
    return body


@router.post("/ask", response_class=EventSourceResponse)
async def ask_question(request: Request, body: AskIn = Depends(start_question)) -> AsyncIterable[ServerSentEvent]:
    """Stream progress and retry waits, then the checked answer (or an error) (FR-006, FR-011)."""
    lock = request.app.state.paperpilot.question_lock
    history = [Turn(turn.role, turn.text) for turn in body.history]

    def work(emit):
        before = llm.request_counts()
        answer = service.ask(body.question, paper_ids=body.paper_ids, k=body.k, history=history, on_event=emit)
        return answer, llm.request_counts() - before

    async for item in run_streaming(work, on_finished=lock.release):
        if item[0] == "event":
            kind, detail = item[1], item[2]
            if kind == "retry_wait":
                yield ServerSentEvent(event="retry_wait", data=detail)
            else:
                yield ServerSentEvent(event="progress", data={"step": kind, **detail})
        elif item[0] == "result":
            answer, requests = item[1]
            yield ServerSentEvent(event="answer", data=answer_body(answer, requests))
        else:
            yield ServerSentEvent(event="error", data=error_for(item[1]).body())


@router.get("/papers")
def get_papers() -> dict:
    """The library's paper cards, sorted by title, and the passage total (FR-019)."""
    papers = library.list_papers()
    cards = [{key: value for key, value in asdict(p).items() if key != "source_file"} for p in papers]
    return {"papers": cards, "total_passages": sum(p.passage_count for p in papers)}


@router.post("/papers", status_code=202)
async def upload_papers(request: Request, files: list[UploadFile] = File(...)) -> dict:
    """Queue one job per dropped file; rejected files get a job that has already failed (FR-016)."""
    jobs = [await request.app.state.jobs.add_upload(upload) for upload in files]
    return {"jobs": [{"job_id": job.job_id, "file_name": job.file_name} for job in jobs]}


@router.get("/jobs")
def get_jobs(request: Request) -> dict:
    """Every recent job: for page load, reconnects and polling."""
    return {"jobs": request.app.state.jobs.snapshot()}


@router.get("/jobs/events", response_class=EventSourceResponse)
async def job_events(request: Request) -> AsyncIterable[ServerSentEvent]:
    """Unfinished jobs, then a `job` event on every change (FR-017); pings keep it open."""
    async for body in request.app.state.jobs.events():
        yield ServerSentEvent(event="job", data=body)


@router.post("/papers/{paper_id}/reprocess", status_code=202)
def reprocess_paper(paper_id: str, request: Request) -> dict:
    """Re-process a paper from its stored PDF as a job (FR-018a)."""
    try:
        library.pdf_path(paper_id)
    except UnknownPaperError:
        raise ApiError("unknown_paper", paper_id=paper_id) from None
    except PdfMissingError:
        raise ApiError("pdf_missing", paper_id=paper_id) from None
    title = store.paper_metadata(paper_id)[0]["title"]
    job = request.app.state.jobs.add_reprocess(paper_id, title)
    return {"job_id": job.job_id, "file_name": job.file_name}


@router.delete("/papers/{paper_id}")
def delete_paper(paper_id: str) -> dict:
    """Remove a paper's passages, PDF and layout (FR-018)."""
    try:
        return {"removed_passages": library.delete_paper(paper_id)}
    except UnknownPaperError:
        raise ApiError("unknown_paper", paper_id=paper_id) from None


@router.get("/passages/{passage_id}")
def get_passage(passage_id: str) -> dict:
    """One cited passage with its highlight layout; reads files only, never parses (FR-012, FR-013)."""
    try:
        view = library.get_passage(passage_id)
    except UnknownPassageError:
        raise ApiError("unknown_passage", passage_id=passage_id) from None
    body = asdict(view)
    if view.layout is not None:
        body["layout"] = {"pages": view.layout.pages, "regions": [asdict(r) for r in view.layout.regions]}
    return body


@router.get("/papers/{paper_id}/pdf")
def get_pdf(paper_id: str) -> FileResponse:
    """The stored PDF, shown inline by the viewer and by "Open full PDF" (FR-014)."""
    try:
        path = library.pdf_path(paper_id)
    except UnknownPaperError:
        raise ApiError("unknown_paper", paper_id=paper_id) from None
    except PdfMissingError:
        raise ApiError("pdf_missing", paper_id=paper_id) from None
    return FileResponse(path, media_type="application/pdf", content_disposition_type="inline",
                        filename=f"{paper_id}.pdf")
