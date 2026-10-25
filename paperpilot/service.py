"""Question answering, summaries and comparisons over the paper library (ADR-0004, ADR-0008).

`ask()` orchestrates: retrieve passages with Feature 1 search, number them, ask the model via
`llm.generate` (the only LLM boundary) and check the reply's citations in code. `summarize()`
does the same per summary section, then writes a TL;DR from the verified sections only.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from paperpilot import library, llm, prompts
from paperpilot.config import load_settings
from paperpilot.errors import EmptyQueryError, LLMError, UnknownPaperError
from paperpilot.prompts import CitationReport, NumberedPassage, Turn, VerifiedSection

__all__ = ["Answer", "Part", "Summary", "Turn", "ask", "number_passages", "review_reply", "summarize"]

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


def number_passages(
    results: list[library.SearchResult], seen: dict[str, NumberedPassage] | None = None
) -> list[NumberedPassage]:
    """Number search results for the model. `seen` (passage id -> numbered passage) carries the
    numbers of earlier calls in the same run, so a passage keeps its first number (FR-004)."""
    seen = {} if seen is None else seen
    numbered: list[NumberedPassage] = []
    for r in results:
        if r.passage_id not in seen:
            seen[r.passage_id] = NumberedPassage(
                number=len(seen) + 1,
                passage_id=r.passage_id,
                paper_id=r.paper_id,
                title=r.title,
                section=r.section,
                page=r.page,
                score=r.score,
                text=r.text,
            )
        numbered.append(seen[r.passage_id])
    return numbered


def _provided(allowed: set[int]) -> str:
    """The provided passage numbers for a warning: "[1]-[6]" for a run, else "[5], [7]"."""
    numbers = sorted(allowed)
    if len(numbers) > 1 and numbers == list(range(numbers[0], numbers[-1] + 1)):
        return f"[{numbers[0]}]-[{numbers[-1]}]"
    return ", ".join(f"[{n}]" for n in numbers) or "none"


def review_reply(
    text: str, passage_count: int | None = None, allowed: set[int] | None = None
) -> tuple[str, CitationReport, str | None, str | None, str | None]:
    """Check a model reply's citations against the passages it was given (FR-008a, FR-009).

    `allowed` holds those passage numbers (a summary section or comparison cell, research R1);
    `passage_count=n` is the answer's case, allowed = {1..n}.
    Returns (answer_text, citations, warning, rejected_answer, fallback_reason). Invalid or
    missing citations replace the answer with NOT_FOUND and keep the original as
    rejected_answer; uncited sentences in an otherwise valid answer only produce a warning.
    """
    if allowed is None:
        allowed = set(range(1, (passage_count or 0) + 1))
    text = text.strip()
    if prompts.is_not_found(text):
        return prompts.NOT_FOUND, NO_CITATIONS, None, None, "model_not_found"
    citations = prompts.check_citations(text, allowed=allowed)
    if citations.invalid:
        numbers = ", ".join(f"[{n}]" for n in citations.invalid)
        warning = (f"The answer was rejected: it cited {numbers}, but only passages "
                   f"{_provided(allowed)} were provided.")
        return prompts.NOT_FOUND, citations, warning, text, "invalid_citations"
    if not citations.valid:
        warning = "The answer was rejected: it had no citations to the provided passages."
        return prompts.NOT_FOUND, citations, warning, text, "no_citations"
    warning = None
    if citations.uncited_sentences:
        warning = "Sentences without a citation: " + " | ".join(citations.uncited_sentences)
    return text, citations, warning, None, None


def ask(
    question: str,
    paper_ids: list[str] | None = None,
    k: int | None = None,
    history: list[Turn] | None = None,
    on_event: Callable[[str, dict], None] | None = None,
) -> Answer:
    """Answer a question from the library with [n] citations to the returned passages.

    `on_event(kind, detail)`, if given, is told the progress (spec FR-006): "rewriting",
    "searching", "reading" ({passages, papers}), "generating", "retry_wait" ({attempt,
    max_attempts, wait_seconds, reason}) and "checking". Events never carry answer text.

    Raises EmptyQueryError for an empty question, UnknownPaperError for an unknown paper filter,
    SettingsError for missing LLM settings and LLMError when the model fails.
    """

    def emit(kind: str, detail: dict | None = None) -> None:
        if on_event is not None:
            on_event(kind, detail or {})

    def on_retry(notice: llm.RetryNotice) -> None:
        emit("retry_wait", asdict(notice))

    if not question or not question.strip():
        raise EmptyQueryError("The question is empty")
    question = question.strip()
    settings = load_settings()
    k = settings.top_k if k is None else k
    timings = {"rewrite": 0.0, "retrieve": 0.0, "generate": 0.0}
    tokens: dict[str, int] = {}

    llm_calls = 0
    standalone, rewrite_applied, rewrite_fallback_reason = question, False, None

    def finish(
        text: str,
        citations: CitationReport,
        fallback_reason: str | None = None,
        warning: str | None = None,
        rejected_answer: str | None = None,
    ) -> Answer:
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
            warning=warning,
            rejected_answer=rejected_answer,
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
        emit("rewriting")
        try:
            rewrite = llm.generate(
                prompts.REWRITE_INSTRUCTION, prompts.build_rewrite_prompt(history, question), on_retry=on_retry
            )
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
    emit("searching")
    results = library.search(standalone, k=k, paper_ids=paper_ids)
    timings["retrieve"] = time.perf_counter() - start
    passages: list[NumberedPassage] = []
    if not results:
        return finish(prompts.NOT_FOUND, NO_CITATIONS, "no_passages")
    # The threshold was calibrated on top-1 scores, so it gates the question on its best passage;
    # when that passes, all k passages go to the model unfiltered (research R8).
    if max(r.score for r in results) < settings.relevance_threshold:
        return finish(prompts.NOT_FOUND, NO_CITATIONS, "below_threshold")
    passages = number_passages(results)
    emit("reading", {"passages": len(passages), "papers": len({p.paper_id for p in passages})})

    start = time.perf_counter()
    emit("generating")
    reply = llm.generate(
        prompts.SYSTEM_INSTRUCTION, prompts.build_answer_prompt(standalone, passages), on_retry=on_retry
    )
    timings["generate"] = time.perf_counter() - start
    llm_calls += 1
    _add_tokens(tokens, reply)

    emit("checking")
    text, citations, warning, rejected_answer, fallback_reason = review_reply(reply.text, len(passages))
    if rejected_answer is not None:
        logger.warning("%s", warning)
    return finish(text, citations, fallback_reason, warning, rejected_answer)


# --- Feature 4: summaries (spec US1, research R1-R3, ADR-0008) ---

SUMMARY_PASSAGES = 4  # passages per summary section (clarification, research R2)
TLDR = "tldr"


@dataclass(frozen=True)
class Part:
    """One summary section, the TL;DR or one comparison cell, after its check (data-model.md).

    `text` is set only when the part is verified; `rejected_text` only when it is held back.
    """

    part: str
    state: str  # verified, not_reported, held_back, failed, not_started
    text: str | None = None
    citations: CitationReport = NO_CITATIONS
    warning: str | None = None
    rejected_text: str | None = None
    reason: str | None = None
    sources: list[list[str]] = field(default_factory=list)
    passages: list[int] = field(default_factory=list)
    requests: dict[str, int] = field(default_factory=lambda: {"planned": 0, "retries": 0})
    tokens: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Summary:
    """A paper's TL;DR and five sections with their numbered passages (data-model.md)."""

    paper_id: str
    title: str
    arxiv_id: str | None
    tldr: Part
    sections: list[Part]
    passages: list[NumberedPassage]
    plan: dict[str, int]
    requests: dict[str, int]
    model: str
    prompt_version: int
    created_at: str
    status: str = "current"  # or "stale" (research R6)
    stale_reason: str | None = None

    @property
    def verified_parts(self) -> int:
        """How many of the six parts are verified (the "All citations verified" badge needs 6)."""
        return sum(1 for p in [self.tldr, *self.sections] if p.state == "verified")


def part_body(part: Part) -> dict:
    """A part as plain data, for events and saving."""
    return asdict(part)


def _paper(paper_id: str) -> library.PaperSummary:
    for paper in library.list_papers():
        if paper.paper_id == paper_id:
            return paper
    raise UnknownPaperError(f"Paper {paper_id} is not in the library")


def _section_part(facet: str, reply_text: str, allowed: set[int], **extra) -> Part:
    """Judge one section reply with the answer validator, scoped to its own passages (FR-011)."""
    if prompts.is_not_reported(reply_text):
        return Part(facet, "not_reported", reason="model_not_found", **extra)
    text, citations, warning, rejected, reason = review_reply(reply_text, allowed=allowed)
    if reason == "invalid_citations":
        return Part(facet, "held_back", citations=citations, warning=warning, rejected_text=rejected,
                    reason=reason, **extra)
    if reason is not None:  # no citations, or the not-found sentence
        return Part(facet, "not_reported", citations=citations, reason=reason, **extra)
    return Part(facet, "verified", text=text, citations=citations, warning=warning, **extra)


def _tldr_part(reply_text: str, sections: list[VerifiedSection], **extra) -> Part:
    """Judge the TL;DR with check_tldr (research R3): only this part is held back on failure."""
    check = prompts.check_tldr(reply_text, sections)
    if check.not_found:
        return Part(TLDR, "not_reported", reason="model_not_found", **extra)
    if not check.ok:
        return Part(TLDR, "held_back", citations=check.citations, warning="; ".join(check.problems),
                    rejected_text=reply_text.strip(), reason="tldr_check", sources=check.sources, **extra)
    return Part(TLDR, "verified", text=reply_text.strip(), citations=check.citations, sources=check.sources,
                **extra)


def summarize(
    paper_id: str,
    regenerate: bool = False,
    retry_parts: list[str] | None = None,
    on_event: Callable[[str, dict], None] | None = None,
) -> Summary:
    """Summarize one paper: per facet, retrieve 4 passages from it, generate, check; then the
    TL;DR from the verified sections (FR-002-FR-005).

    `on_event(kind, detail)` receives "plan", "progress" ({part, step, passages?}), "retry_wait"
    ({part, ...}) and "part" (a checked part). No event carries text before its part's check.
    Raises UnknownPaperError, SettingsError.
    """

    def emit(kind: str, detail: dict) -> None:
        if on_event is not None:
            on_event(kind, detail)

    paper = _paper(paper_id)
    settings = load_settings()
    parts_order = [*prompts.FACETS, TLDR]
    plan = {"max_requests": len(parts_order)}
    emit("plan", {**plan, "parts": parts_order})

    seen: dict[str, NumberedPassage] = {}
    sections: list[Part] = []
    verified: list[VerifiedSection] = []

    def generate(part: str, system: str, prompt: str) -> tuple[llm.LLMReply, dict[str, int], dict[str, int]]:
        before = llm.request_counts().retries
        reply = llm.generate(system, prompt,
                             on_retry=lambda notice: emit("retry_wait", {"part": part, **asdict(notice)}))
        tokens: dict[str, int] = {}
        _add_tokens(tokens, reply)
        return reply, {"planned": 1, "retries": llm.request_counts().retries - before}, tokens

    for key, facet in prompts.FACETS.items():
        emit("progress", {"part": key, "step": "searching"})
        results = library.search(facet.query, k=SUMMARY_PASSAGES, paper_ids=[paper_id])
        if not results or max(r.score for r in results) < settings.relevance_threshold:
            part = Part(key, "not_reported", reason="no_passages" if not results else "below_threshold")
        else:
            numbered = number_passages(results, seen)
            numbers = [p.number for p in numbered]
            emit("progress", {"part": key, "step": "reading", "passages": len(numbered)})
            emit("progress", {"part": key, "step": "generating"})
            reply, requests, tokens = generate(key, prompts.SECTION_INSTRUCTION,
                                               prompts.build_section_prompt(key, numbered))
            emit("progress", {"part": key, "step": "checking"})
            part = _section_part(key, reply.text, set(numbers), passages=numbers, requests=requests,
                                 tokens=tokens)
            if part.state == "verified":
                verified.append(VerifiedSection(facet.label, part.text or "", part.citations.valid))
        sections.append(part)
        emit("part", part_body(part))

    if not verified:
        tldr = Part(TLDR, "not_reported", reason="no_verified_sections")
    else:
        emit("progress", {"part": TLDR, "step": "generating"})
        reply, requests, tokens = generate(TLDR, prompts.TLDR_INSTRUCTION, prompts.build_tldr_prompt(verified))
        emit("progress", {"part": TLDR, "step": "checking"})
        cited = sorted({n for v in verified for n in v.citations})
        tldr = _tldr_part(reply.text, verified, passages=cited, requests=requests, tokens=tokens)
    emit("part", part_body(tldr))

    all_parts = [*sections, tldr]
    summary = Summary(
        paper_id=paper_id,
        title=paper.title,
        arxiv_id=paper.arxiv_id,
        tldr=tldr,
        sections=sections,
        passages=sorted(seen.values(), key=lambda p: p.number),
        plan=plan,
        requests={k: sum(p.requests[k] for p in all_parts) for k in ("planned", "retries")},
        model=settings.llm_model,
        prompt_version=prompts.SUMMARY_PROMPT_VERSION,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    logger.info("Summarized %s: %d of 6 parts verified, %d requests", paper_id, summary.verified_parts,
                summary.requests["planned"])
    return summary
