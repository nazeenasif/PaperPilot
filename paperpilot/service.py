"""Question answering over the paper library (contracts/answer-api.md, ADR-0004).

`ask()` orchestrates: retrieve passages with Feature 1 search, number them, ask the model via
`llm.generate` (the only LLM boundary) and check the reply's citations in code.
"""

import logging
import time
from dataclasses import dataclass

from paperpilot import library, llm, prompts
from paperpilot.config import load_settings
from paperpilot.errors import EmptyQueryError
from paperpilot.prompts import CitationReport, NumberedPassage, Turn

__all__ = ["Answer", "Turn", "ask"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Answer:
    """An answer with its numbered passages, citation report, fallback reasons, timings and tokens."""

    question: str
    standalone_question: str
    rewrite_applied: bool
    text: str
    not_found: bool
    passages: list[NumberedPassage]
    citations: CitationReport
    warning: str | None
    rejected_answer: str | None
    fallback_reason: str | None
    rewrite_fallback_reason: str | None
    word_count: int
    llm_calls: int
    timings: dict[str, float]
    tokens: dict[str, int]


def _add_tokens(totals: dict[str, int], reply: llm.LLMReply) -> None:
    for key, value in (
        ("input", reply.input_tokens),
        ("output", reply.output_tokens),
        ("reasoning", reply.reasoning_tokens),
    ):
        if value is not None:
            totals[key] = totals.get(key, 0) + value


def _number(results: list[library.SearchResult]) -> list[NumberedPassage]:
    return [
        NumberedPassage(
            number=i,
            passage_id=r.passage_id,
            paper_id=r.paper_id,
            title=r.title,
            section=r.section,
            page=r.page,
            score=r.score,
            text=r.text,
        )
        for i, r in enumerate(results, start=1)
    ]


def ask(
    question: str,
    paper_ids: list[str] | None = None,
    k: int | None = None,
    history: list[Turn] | None = None,
) -> Answer:
    """Answer a question from the library with [n] citations to the returned passages.

    Raises EmptyQueryError for an empty question, UnknownPaperError for an unknown paper filter,
    SettingsError for missing LLM settings and LLMError when the model fails.
    """
    if not question or not question.strip():
        raise EmptyQueryError("The question is empty")
    question = question.strip()
    settings = load_settings()
    k = settings.top_k if k is None else k
    timings = {"rewrite": 0.0, "retrieve": 0.0, "generate": 0.0}
    tokens: dict[str, int] = {}

    start = time.perf_counter()
    passages = _number(library.search(question, k=k, paper_ids=paper_ids))
    timings["retrieve"] = time.perf_counter() - start

    start = time.perf_counter()
    reply = llm.generate(prompts.SYSTEM_INSTRUCTION, prompts.build_answer_prompt(question, passages))
    timings["generate"] = time.perf_counter() - start
    _add_tokens(tokens, reply)

    text = reply.text.strip()
    citations = prompts.check_citations(text, len(passages))
    logger.info("Answered with %d passages in %.2f s", len(passages), sum(timings.values()))
    return Answer(
        question=question,
        standalone_question=question,
        rewrite_applied=False,
        text=text,
        not_found=False,
        passages=passages,
        citations=citations,
        warning=None,
        rejected_answer=None,
        fallback_reason=None,
        rewrite_fallback_reason=None,
        word_count=prompts.word_count(text),
        llm_calls=1,
        timings=timings,
        tokens=tokens,
    )
