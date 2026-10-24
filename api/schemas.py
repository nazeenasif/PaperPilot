"""Response and request models for the web API (contracts/web-api.md)."""

from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel, Field

from paperpilot.llm import RequestCounts
from paperpilot.service import Answer


class StatusOut(BaseModel):
    """GET /api/status: always answers, even while the model is loading."""

    state: Literal["loading", "ready", "error"]
    model: str
    model_is_free: bool
    daily_limit: int


class TurnIn(BaseModel):
    """One earlier message of the conversation."""

    role: Literal["user", "assistant"]
    text: str = Field(max_length=20_000)


class AskIn(BaseModel):
    """POST /api/ask body."""

    question: str = Field(max_length=2_000)
    paper_ids: list[str] | None = None
    k: int | None = Field(default=None, ge=1, le=20)
    history: list[TurnIn] = Field(default_factory=list, max_length=50)


def answer_body(answer: Answer, requests: RequestCounts, usage: dict | None = None) -> dict:
    """The `answer` event payload: everything ask() returns plus verified and papers_read (FR-004)."""
    return {
        "question": answer.question,
        "standalone_question": answer.standalone_question,
        "rewrite_applied": answer.rewrite_applied,
        "rewrite_fallback_reason": answer.rewrite_fallback_reason,
        "text": answer.text,
        "not_found": answer.not_found,
        "fallback_reason": answer.fallback_reason,
        "warning": answer.warning,
        "rejected_answer": answer.rejected_answer,
        "citations": asdict(answer.citations),
        # The badge claims only what the code checked (FR-005).
        "verified": not answer.not_found and not answer.citations.invalid,
        "passages": [asdict(p) for p in answer.passages],
        "papers_read": len({p.paper_id for p in answer.passages}),
        "word_count": answer.word_count,
        "llm_calls": answer.llm_calls,
        "requests": {"planned": requests.planned, "retries": requests.retries},
        "timings": answer.timings,
        "tokens": answer.tokens,
        "usage": usage,  # filled once request accounting exists (US5, ADR-0007)
    }
