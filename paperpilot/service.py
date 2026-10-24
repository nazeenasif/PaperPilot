"""Question answering over the paper library (contracts/answer-api.md, ADR-0004).

`ask()` orchestrates: retrieve passages with Feature 1 search, number them, ask the model via
`llm.generate` (the only LLM boundary) and check the reply's citations in code.
"""

import logging
import time
from dataclasses import dataclass

from paperpilot import library, llm, prompts
from paperpilot.config import load_settings
from paperpilot.errors import EmptyQueryError, LLMError
from paperpilot.prompts import CitationReport, NumberedPassage, Turn

__all__ = ["Answer", "Turn", "ask"]

logger = logging.getLogger(__name__)

NO_CITATIONS = CitationReport(valid=[], invalid=[], uncited_sentences=[])


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

    llm_calls = 0
    standalone, rewrite_applied, rewrite_fallback_reason = question, False, None

    def finish(text: str, citations: CitationReport, fallback_reason: str | None = None) -> Answer:
        logger.info("Answered (%s) with %d passages in %.2f s",
                    fallback_reason or "answer", len(passages), sum(timings.values()))
        return Answer(
            question=question,
            standalone_question=standalone,
            rewrite_applied=rewrite_applied,
            text=text,
            not_found=text == prompts.NOT_FOUND,
            passages=passages,
            citations=citations,
            warning=None,
            rejected_answer=None,
            fallback_reason=fallback_reason,
            rewrite_fallback_reason=rewrite_fallback_reason,
            word_count=prompts.word_count(text),
            llm_calls=llm_calls,
            timings=timings,
            tokens=tokens,
        )

    if history:
        # Turn a follow-up into a standalone question; fall back to the original (FR-010–FR-012).
        start = time.perf_counter()
        try:
            rewrite = llm.generate(prompts.REWRITE_INSTRUCTION, prompts.build_rewrite_prompt(history, question))
        except LLMError as error:
            logger.info("Rewrite failed, using the original question: %s", error)
            rewrite_fallback_reason = "rewrite_failed"
        else:
            _add_tokens(tokens, rewrite)
            cleaned = prompts.clean_rewrite(rewrite.text)
            if cleaned:
                standalone, rewrite_applied = cleaned, True
            else:
                rewrite_fallback_reason = "rewrite_empty"
        llm_calls += 1
        timings["rewrite"] = time.perf_counter() - start

    start = time.perf_counter()
    results = library.search(standalone, k=k, paper_ids=paper_ids)
    timings["retrieve"] = time.perf_counter() - start
    passages: list[NumberedPassage] = []
    if not results:
        return finish(prompts.NOT_FOUND, NO_CITATIONS, "no_passages")
    # The threshold was calibrated on top-1 scores, so it gates the question on its best passage;
    # when that passes, all k passages go to the model unfiltered (research R8).
    if max(r.score for r in results) < settings.relevance_threshold:
        return finish(prompts.NOT_FOUND, NO_CITATIONS, "below_threshold")
    passages = _number(results)

    start = time.perf_counter()
    reply = llm.generate(prompts.SYSTEM_INSTRUCTION, prompts.build_answer_prompt(standalone, passages))
    timings["generate"] = time.perf_counter() - start
    llm_calls += 1
    _add_tokens(tokens, reply)

    text = reply.text.strip()
    if prompts.is_not_found(text):
        return finish(prompts.NOT_FOUND, NO_CITATIONS, "model_not_found")
    return finish(text, prompts.check_citations(text, len(passages)))
