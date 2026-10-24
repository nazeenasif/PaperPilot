"""HTTP endpoints (contracts/web-api.md). Each one calls the engine and maps the result."""

from fastapi import APIRouter, Request

from api.schemas import StatusOut
from paperpilot.config import Settings

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
