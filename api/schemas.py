"""Response and request models for the web API (contracts/web-api.md)."""

from typing import Literal

from pydantic import BaseModel


class StatusOut(BaseModel):
    """GET /api/status: always answers, even while the model is loading."""

    state: Literal["loading", "ready", "error"]
    model: str
    model_is_free: bool
    daily_limit: int
