"""HTTP endpoints (contracts/web-api.md). Each one calls the engine and maps the result."""

from collections.abc import AsyncIterable
from dataclasses import asdict

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent

from api.errors import ApiError, error_for
from api.schemas import AskIn, CompareIn, SearchIn, StatusOut, SummarizeIn, answer_body, comparison_body, summary_body, usage_body
from api.streams import run_streaming
from paperpilot import library, llm, prompts, service, store
from paperpilot.config import Settings
from paperpilot.errors import DailyLimitError, PdfMissingError, UnknownPaperError, UnknownPassageError
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


@router.get("/usage")
def get_usage(request: Request) -> dict:
    """Today's model requests; the provider is asked at most every 30 s (FR-024)."""
    return usage_body(request.app.state.usage.get())


def check_scope(paper_ids: list[str] | None) -> None:
    """An explicit selection must name at least one paper, and only known ones."""
    if paper_ids is not None:
        if not paper_ids:
            raise ApiError("no_papers_selected")
        for paper_id in paper_ids:
            if not store.has_paper(paper_id):
                raise ApiError("unknown_paper", paper_id=paper_id)


@router.post("/search")
def search_passages(body: SearchIn) -> dict:
    """Ranked passages without the model ("Browse passages instead", FR-026)."""
    if not body.query.strip():
        raise ApiError("empty_question")
    check_scope(body.paper_ids)
    results = library.search(body.query, k=body.k, paper_ids=body.paper_ids)
    return {"results": [asdict(result) for result in results]}


def start_question(body: AskIn, request: Request) -> AskIn:
    """Validate before the stream starts (plain JSON errors) and take the one-question lock."""
    if not body.question.strip():
        raise ApiError("empty_question")
    check_scope(body.paper_ids)
    if not request.app.state.paperpilot.model_lock.acquire(blocking=False):
        raise ApiError("busy_task")
    return body


@router.post("/ask", response_class=EventSourceResponse)
async def ask_question(request: Request, body: AskIn = Depends(start_question)) -> AsyncIterable[ServerSentEvent]:
    """Stream progress and retry waits, then the checked answer (or an error) (FR-006, FR-011)."""
    lock = request.app.state.paperpilot.model_lock
    usage = request.app.state.usage
    history = [Turn(turn.role, turn.text) for turn in body.history]

    def work(emit):
        before = llm.request_counts()
        answer = service.ask(body.question, paper_ids=body.paper_ids, k=body.k, history=history, on_event=emit)
        return answer, llm.request_counts() - before, usage_body(usage.get())

    async for item in run_streaming(work, on_finished=lock.release):
        if item[0] == "event":
            kind, detail = item[1], item[2]
            if kind == "retry_wait":
                yield ServerSentEvent(event="retry_wait", data=detail)
            else:
                yield ServerSentEvent(event="progress", data={"step": kind, **detail})
        elif item[0] == "result":
            answer, requests, today = item[1]
            yield ServerSentEvent(event="answer", data=answer_body(answer, requests, today))
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


# --- Feature 4: summaries (contracts/web-api.md; spec US1, US2) ---

SUMMARY_PARTS = {*prompts.FACETS, service.TLDR}


def _check_budget(needed: int) -> None:
    """Refuse a run before its stream when fewer requests remain than its plan (FR-023)."""
    try:
        service.check_request_budget(needed)
    except DailyLimitError as error:
        raise error_for(error) from None


@router.get("/summaries")
def list_summaries() -> dict:
    """Every paper with its saved summary's status, for the Summarize tab (FR-001). No model request."""
    papers = []
    for paper in library.list_papers():
        saved = service.saved_summary(paper.paper_id)
        papers.append({
            "paper_id": paper.paper_id,
            "title": paper.title,
            "arxiv_id": paper.arxiv_id,
            "summary": {
                "status": saved.status if saved else "none",
                "created_at": saved.created_at if saved else None,
                "model": saved.model if saved else None,
            },
        })
    return {"papers": papers, "plan": service.summary_plan("")}


@router.get("/summaries/{paper_id}")
def get_summary(paper_id: str) -> dict:
    """The saved summary, current or stale (with its reason) and the plan for regenerating it.
    404 not_saved (with the plan) when there is none. Never sends a model request (FR-016)."""
    if not store.has_paper(paper_id):
        raise ApiError("unknown_paper", paper_id=paper_id)
    saved = service.saved_summary(paper_id)
    if saved is None:
        raise ApiError("not_saved", plan=service.summary_plan(paper_id))
    return {**summary_body(saved), "plan": service.summary_plan(paper_id)}


def start_summary(paper_id: str, body: SummarizeIn, request: Request) -> SummarizeIn:
    """Validate before the stream starts (plain JSON errors) and take the one-task lock."""
    if not store.has_paper(paper_id):
        raise ApiError("unknown_paper", paper_id=paper_id)
    if body.retry_parts is not None:
        if not body.retry_parts or any(part not in SUMMARY_PARTS for part in body.retry_parts):
            raise ApiError("invalid_request")
        saved = service.saved_summary(paper_id)
        if saved is None:
            raise ApiError("not_saved", plan=service.summary_plan(paper_id))
        if saved.status == "stale":
            raise ApiError("invalid_request")
    if body.retry_parts is not None:
        _check_budget(service.summary_plan(paper_id, body.retry_parts)["max_requests"])
    elif body.regenerate or service.saved_summary(paper_id) is None:
        _check_budget(service.summary_plan(paper_id)["max_requests"])
    if not request.app.state.paperpilot.model_lock.acquire(blocking=False):
        raise ApiError("busy_task")
    return body


@router.post("/summaries/{paper_id}", response_class=EventSourceResponse)
async def summarize_paper(
    paper_id: str, request: Request, body: SummarizeIn = Depends(start_summary)
) -> AsyncIterable[ServerSentEvent]:
    """Stream the plan, per-part progress and checked parts, then the saved summary (FR-012)."""
    lock = request.app.state.paperpilot.model_lock

    def work(emit):
        return service.summarize(paper_id, regenerate=body.regenerate, retry_parts=body.retry_parts,
                                 on_event=emit)

    async for item in run_streaming(work, on_finished=lock.release):
        if item[0] == "event":
            yield ServerSentEvent(event=item[1], data=item[2])
        elif item[0] == "result":
            yield ServerSentEvent(event="summary", data=summary_body(item[1]))
        else:
            yield ServerSentEvent(event="error", data=error_for(item[1]).body())


# --- Feature 4: comparisons (contracts/web-api.md; spec US3) ---


def _checked_comparison(paper_ids: list[str], aspects: list[str]) -> None:
    """Refuse a bad comparison before anything else (plain JSON errors)."""
    try:
        service.check_comparison(paper_ids, aspects)
    except ValueError:
        raise ApiError("invalid_request") from None
    except UnknownPaperError:
        raise ApiError("unknown_paper") from None


@router.get("/comparisons")
def get_comparison(papers: str, aspects: str) -> dict:
    """The saved comparison in any paper and aspect order, current or stale, and the plan for
    running it. 404 not_saved (with the plan) when there is none. Never sends a model request."""
    paper_ids, wanted = papers.split(","), aspects.split(",")
    _checked_comparison(paper_ids, wanted)
    plan = service.comparison_plan(paper_ids, wanted)
    saved = service.saved_comparison(paper_ids, wanted)
    if saved is None:
        raise ApiError("not_saved", plan=plan)
    return {**comparison_body(saved), "plan": plan}


def start_comparison(body: CompareIn, request: Request) -> CompareIn:
    """Validate before the stream starts (plain JSON errors) and take the one-task lock."""
    _checked_comparison(body.paper_ids, body.aspects)
    if body.retry_aspects is not None:
        if not body.retry_aspects or set(body.retry_aspects) - set(body.aspects):
            raise ApiError("invalid_request")
        saved = service.saved_comparison(body.paper_ids, body.aspects)
        if saved is None:
            raise ApiError("not_saved", plan=service.comparison_plan(body.paper_ids, body.aspects))
        if saved.status == "stale":
            raise ApiError("invalid_request")
    if body.retry_aspects is not None:
        _check_budget(len(body.retry_aspects))
    elif body.regenerate or service.saved_comparison(body.paper_ids, body.aspects) is None:
        _check_budget(len(body.aspects))
    if not request.app.state.paperpilot.model_lock.acquire(blocking=False):
        raise ApiError("busy_task")
    return body


@router.post("/comparisons", response_class=EventSourceResponse)
async def compare_papers(request: Request, body: CompareIn = Depends(start_comparison)) -> AsyncIterable[ServerSentEvent]:
    """Stream the plan, per-aspect progress and checked cells, then the saved comparison (FR-012)."""
    lock = request.app.state.paperpilot.model_lock

    def work(emit):
        return service.compare(body.paper_ids, body.aspects, regenerate=body.regenerate,
                               retry_aspects=body.retry_aspects, on_event=emit)

    async for item in run_streaming(work, on_finished=lock.release):
        if item[0] == "event":
            yield ServerSentEvent(event=item[1], data=item[2])
        elif item[0] == "result":
            yield ServerSentEvent(event="comparison", data=comparison_body(item[1]))
        else:
            yield ServerSentEvent(event="error", data=error_for(item[1]).body())
