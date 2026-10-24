"""HTTP endpoints (contracts/web-api.md). Each one calls the engine and maps the result."""

from collections.abc import AsyncIterable

from fastapi import APIRouter, Depends, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from api.errors import ApiError, error_for
from api.schemas import AskIn, StatusOut, answer_body
from api.streams import run_streaming
from paperpilot import llm, service, store
from paperpilot.config import Settings
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
