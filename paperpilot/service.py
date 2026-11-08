"""Question answering, summaries and comparisons over the paper library (ADR-0004, ADR-0008).

`ask()` orchestrates: retrieve passages with Feature 1 search, number them, ask the model via
`llm.generate` (the only LLM boundary) and check the reply's citations in code. `summarize()`
does the same per summary section, then writes a TL;DR from the verified sections only.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone

from paperpilot import library, llm, prompts, store
from paperpilot.config import load_settings
from paperpilot.errors import (
    DailyLimitError,
    EmptyQueryError,
    LLMError,
    RateLimitedError,
    RowFormatError,
    UnknownPaperError,
)
from paperpilot.prompts import CitationReport, NumberedPassage, Turn, VerifiedSection

__all__ = [
    "Answer", "Part", "Summary", "Turn", "ask", "number_passages", "review_reply", "saved_summary",
    "summarize", "summary_from_dict", "summary_plan", "summary_to_dict",
]

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
    built_from: list[str] = field(default_factory=list)  # TL;DR only: sections whose text it used
    built_without: list[str] = field(default_factory=list)  # TL;DR only: failed or since regenerated
    passages: list[int] = field(default_factory=list)
    requests: dict[str, int] = field(default_factory=lambda: {"planned": 0, "retries": 0})
    tokens: dict[str, int] = field(default_factory=dict)
    until: str | None = None  # not_started: when requests resume (daily limit, long wait)


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
    # A later regeneration that ended with failed parts: {created_at, failed_parts, retry_parts,
    # verified_parts}. Set when read, never saved (FR-019, FR-020).
    pending: dict | None = None

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


PART_FAILURES = {"cut_off", "empty"}  # a failed part; the run goes on (research R5, R8)


class _RunStopped(Exception):
    """A systemic model failure: no further request for this run (research R8, FR-024)."""

    def __init__(self, error: LLMError, requests: dict[str, int]) -> None:
        super().__init__(str(error))
        self.error = error
        self.requests = requests

    @property
    def until(self) -> str | None:
        if isinstance(self.error, DailyLimitError):
            return self.error.resets_at.isoformat()
        if isinstance(self.error, RateLimitedError):
            return self.error.until.isoformat()
        return None


def check_request_budget(needed: int) -> None:
    """Refuse a run before any request when fewer requests remain than its plan (FR-023)."""
    today = llm.usage()
    if today.remaining < needed:
        raise DailyLimitError(today.used, today.limit, today.resets_at, needed=needed)


def _generate_part(part: str, system: str, prompt: str, task: str, emit: Callable[[str, dict], None]):
    """One model request for a part: (reply or None, requests, tokens, failure reason). Raises
    _RunStopped for a failure that should end the run."""
    start = llm.request_counts()
    before = start.retries
    try:
        reply = llm.generate(system, prompt,
                             on_retry=lambda notice: emit("retry_wait", {"part": part, **asdict(notice)}),
                             task=task)
    except LLMError as error:
        if error.reason not in PART_FAILURES:
            used = llm.request_counts() - start
            raise _RunStopped(error, {"planned": used.planned, "retries": used.retries}) from error
        requests = {"planned": 1, "retries": llm.request_counts().retries - before}
        return None, requests, error.tokens or {}, error.reason
    tokens: dict[str, int] = {}
    _add_tokens(tokens, reply)
    return reply, {"planned": 1, "retries": llm.request_counts().retries - before}, tokens, None


def summary_to_dict(summary: Summary) -> dict:
    """A summary as plain data, for saving and the API."""
    return asdict(summary)


def _part_from_dict(data: dict) -> Part:
    return Part(**{**data, "citations": CitationReport(**data["citations"])})


def _built_from(sections: list[Part]) -> tuple[list[str], list[str]]:
    """The sections a TL;DR written now uses, and those it goes without. A section the paper
    does not report is not missing: there was nothing to use."""
    built_from = [s.part for s in sections if s.state == "verified"]
    built_without = [s.part for s in sections if s.state in ("held_back", "failed", "not_started")]
    return built_from, built_without


def summary_from_dict(data: dict) -> Summary:
    """Rebuild a summary saved with summary_to_dict."""
    sections = [_part_from_dict(d) for d in data["sections"]]
    tldr = data["tldr"]
    if "built_from" not in tldr:  # saved before this was recorded; sections could not be retried then
        built_from, built_without = _built_from(sections) if tldr.get("reason") != "no_verified_sections" else ([], [])
        tldr = {**tldr, "built_from": built_from, "built_without": built_without}
    return Summary(**{
        **data,
        "tldr": _part_from_dict(tldr),
        "sections": sections,
        "passages": [NumberedPassage(**d) for d in data["passages"]],
    })


def _summary_key(paper_id: str) -> library.ResultKey:
    return library.result_key("summary", [paper_id])


def _unfinished_key(paper_id: str) -> library.ResultKey:
    return library.result_key("summary_unfinished", [paper_id])


def _unfinished_run(paper_id: str) -> Summary | None:
    """The regeneration left unfinished beside a complete summary; ignored once it is stale."""
    settings = load_settings()
    found = library.load_result(_unfinished_key(paper_id), settings.llm_model, prompts.SUMMARY_PROMPT_VERSION)
    return summary_from_dict(found[0]) if found and found[1] is None else None


def _passage_moved(passage: NumberedPassage) -> bool:
    """True if a citation's passage id no longer holds the text the summary was written from."""
    found = store.get_passage(passage.passage_id)
    return found is None or found[0] != passage.text


def _save(key: library.ResultKey, summary: Summary) -> None:
    library.save_result(key, summary_to_dict(replace(summary, pending=None)), summary.model, summary.prompt_version)


def saved_summary(paper_id: str) -> Summary | None:
    """The saved summary, current or stale (with its reason), and any unfinished regeneration beside
    it; never generates (FR-016, FR-017, FR-020)."""
    settings = load_settings()
    found = library.load_result(_summary_key(paper_id), settings.llm_model, prompts.SUMMARY_PROMPT_VERSION)
    if found is None:
        return None
    data, stale_reason = found
    summary = summary_from_dict(data)
    if stale_reason == "passages_changed":
        summary = replace(summary, passages=[replace(p, moved=_passage_moved(p)) for p in summary.passages])
    unfinished = _unfinished_run(paper_id)
    pending = {
        "created_at": unfinished.created_at,
        "failed_parts": _failed_sections(unfinished),
        "retry_parts": _parts_to_finish(unfinished),
        "verified_parts": unfinished.verified_parts,
    } if unfinished else None
    return replace(summary, status="stale" if stale_reason else "current", stale_reason=stale_reason, pending=pending)


def _retry_facets(retry_parts: list[str]) -> list[str]:
    unknown = [p for p in retry_parts if p not in prompts.FACETS and p != TLDR]
    if unknown or not retry_parts:
        raise ValueError(f"Unknown summary parts to retry: {unknown or retry_parts}")
    return [p for p in prompts.FACETS if p in retry_parts]


def summary_plan(paper_id: str, retry_parts: list[str] | None = None) -> dict[str, int]:
    """The most model requests a summary (or a retry of some parts) can make (FR-021)."""
    if retry_parts is None:
        return {"max_requests": len(prompts.FACETS) + 1}
    return {"max_requests": len(_retry_facets(retry_parts)) + (TLDR in retry_parts)}


@dataclass(frozen=True)
class FacetRetrieval:
    """What a facet reads, and the whole-paper top score the relevance gate judges (None if empty)."""

    passages: list[library.SearchResult]
    gate_score: float | None


def facet_retrieval(facet: str, paper_id: str, k: int = SUMMARY_PASSAGES) -> FacetRetrieval:
    """Search a paper for a facet, for `k` passages. The whole-paper search answers "does this paper
    cover the facet?"; the facet's preferred sections answer "where to read it" (research R2)."""
    spec = prompts.FACETS[facet]
    sections = library.paper_sections(paper_id)
    whole = library.search(spec.query, k=k, paper_ids=[paper_id], sections=spec.searchable(sections))
    gate_score = max((r.score for r in whole), default=None)

    preferred = spec.preferred(sections)
    if not preferred:
        return FacetRetrieval(whole, gate_score)
    # Up to preferred_passages from the preferred sections; the whole paper fills the rest, best first.
    own = library.search(spec.query, k=min(spec.preferred_passages, k), paper_ids=[paper_id], sections=preferred)
    taken = {r.passage_id for r in own}
    others = [r for r in whole if r.passage_id not in taken][:k - len(own)]
    best_first = sorted([*own, *others], key=lambda r: r.score, reverse=True)
    return FacetRetrieval([replace(r, rank=rank) for rank, r in enumerate(best_first, start=1)], gate_score)


def _failed_sections(summary: Summary) -> list[str]:
    return [s.part for s in summary.sections if s.state in ("failed", "not_started")]


def _parts_to_finish(summary: Summary) -> list[str]:
    """What a retry must run: failed sections, and the TL;DR if it failed or misses a section it
    could now use. A held-back section is a finished result, not something to finish."""
    held_back = {s.part for s in summary.sections if s.state == "held_back"}
    tldr_unfinished = summary.tldr.state in ("failed", "not_started") or set(summary.tldr.built_without) - held_back
    return [*_failed_sections(summary), *([TLDR] if tldr_unfinished else [])]


def _complete(summary: Summary) -> bool:
    return not _parts_to_finish(summary)


def summarize(
    paper_id: str,
    regenerate: bool = False,
    retry_parts: list[str] | None = None,
    on_event: Callable[[str, dict], None] | None = None,
) -> Summary:
    """Summarize one paper: per facet, retrieve 4 passages from it, generate, check; then the
    TL;DR from the verified sections (FR-002-FR-005). Saved summaries are reused (FR-016).

    - Default: return the saved summary (current or marked stale) with 0 requests, else generate.
    - `regenerate`: generate anew; the saved summary is replaced only when the new one finished.
      A complete saved summary, current or stale, is kept over a new one with failed parts, whose
      finished parts are saved beside it and reported as `pending` (FR-019, FR-020).
    - `retry_parts`: rerun those parts of the unfinished regeneration if there is one, else of the
      saved summary. A regenerated section leaves the TL;DR marked `built_without` it, until "tldr"
      is regenerated too (FR-020). An unfinished regeneration replaces the saved summary only once
      it is complete.

    `on_event(kind, detail)` receives "plan", "progress" ({part, step, passages?}), "retry_wait"
    ({part, ...}) and "part" (a checked part). No event carries text before its part's check.
    A daily limit, long wait, busy or unavailable model stops the run: finished parts are kept and
    saved, the rest are `not_started` with the reason (FR-024). If nothing had finished, the error
    is raised and nothing is saved.
    Raises UnknownPaperError, SettingsError, ValueError (bad retry_parts or nothing to retry),
    DailyLimitError (fewer requests left than the plan, nothing sent), or the stopping LLMError.
    """
    paper = _paper(paper_id)
    base: Summary | None = None
    unfinished: Summary | None = None
    if retry_parts is not None:
        facets = _retry_facets(retry_parts)
        unfinished = _unfinished_run(paper_id)
        base = unfinished or saved_summary(paper_id)
        if base is None:
            raise ValueError(f"No saved summary of {paper_id} to retry parts of")
        if base.status == "stale":
            raise ValueError(f"The saved summary of {paper_id} is an earlier one; regenerate it in full")
    else:
        facets = list(prompts.FACETS)
        saved = saved_summary(paper_id)
        if saved is not None and not regenerate:
            return saved

    rewrite_tldr = retry_parts is None or TLDR in retry_parts
    check_request_budget(len(facets) + rewrite_tldr)
    summary = _run_summary(paper, facets, rewrite_tldr, base, on_event)
    saved = saved_summary(paper_id)
    keep_saved = saved is not None and _complete(saved) and not _complete(summary)
    if (unfinished is not None or retry_parts is None) and keep_saved:
        logger.warning("Summary run of %s ended with failed parts; kept the saved summary", paper_id)
        _save(_unfinished_key(paper_id), summary)
        return replace(saved_summary(paper_id), requests=summary.requests)
    _save(_summary_key(paper_id), summary)
    library.delete_result(_unfinished_key(paper_id))
    return summary


def _run_summary(
    paper: library.PaperSummary,
    facets: list[str],
    rewrite_tldr: bool,
    base: Summary | None,
    on_event: Callable[[str, dict], None] | None,
) -> Summary:
    """Generate the given sections (the others come from `base`), then the TL;DR if asked."""

    def emit(kind: str, detail: dict) -> None:
        if on_event is not None:
            on_event(kind, detail)

    settings = load_settings()
    paper_id = paper.paper_id
    run_order = [*facets, TLDR] if rewrite_tldr else facets
    plan = {"max_requests": len(run_order)}
    emit("plan", {**plan, "parts": run_order})

    seen: dict[str, NumberedPassage] = {p.passage_id: p for p in base.passages} if base else {}
    kept = {p.part: p for p in base.sections} if base else {}
    sections: list[Part] = []
    verified: list[VerifiedSection] = []
    stopped: _RunStopped | None = None

    for key, facet in prompts.FACETS.items():
        if key not in facets:
            part = kept[key]
        elif stopped:
            part = Part(key, "not_started", reason=stopped.error.reason, until=stopped.until)
            emit("part", part_body(part))
        else:
            emit("progress", {"part": key, "step": "searching"})
            retrieval = facet_retrieval(key, paper_id)
            results = retrieval.passages
            if not results or retrieval.gate_score < settings.relevance_threshold:
                part = Part(key, "not_reported", reason="no_passages" if not results else "below_threshold")
            else:
                numbered = number_passages(results, seen)
                numbers = [p.number for p in numbered]
                emit("progress", {"part": key, "step": "reading", "passages": len(numbered)})
                emit("progress", {"part": key, "step": "generating"})
                try:
                    reply, requests, tokens, failure = _generate_part(
                        key, prompts.SECTION_INSTRUCTION, prompts.build_section_prompt(key, numbered), "summary_section", emit)
                except _RunStopped as stop:
                    if not any(s.part in facets for s in sections):
                        raise stop.error from None  # nothing finished, so nothing to keep
                    stopped = stop
                    reply, requests, tokens, failure = None, stop.requests, {}, None
                if stopped:
                    part = Part(key, "not_started", reason=stopped.error.reason, passages=numbers, requests=requests,
                                until=stopped.until)
                elif failure:
                    part = Part(key, "failed", reason=failure, passages=numbers, requests=requests, tokens=tokens)
                else:
                    emit("progress", {"part": key, "step": "checking"})
                    part = _section_part(key, reply.text, set(numbers), passages=numbers, requests=requests,
                                         tokens=tokens)
            emit("part", part_body(part))
        sections.append(part)
        if part.state == "verified":
            verified.append(VerifiedSection(prompts.FACETS[key].label, part.text or "", part.citations.valid))

    built = dict(zip(("built_from", "built_without"), _built_from(sections)))
    if not rewrite_tldr:
        kept_tldr = base.tldr
        tldr = replace(
            kept_tldr,
            built_from=[k for k in kept_tldr.built_from if k not in facets],
            built_without=[k for k in prompts.FACETS if k in kept_tldr.built_without or k in facets],
        )
    elif stopped:
        tldr = Part(TLDR, "not_started", reason=stopped.error.reason, until=stopped.until, **built)
    elif not verified:
        tldr = Part(TLDR, "not_reported", reason="no_verified_sections")
    else:
        emit("progress", {"part": TLDR, "step": "generating"})
        cited = sorted({n for v in verified for n in v.citations})
        try:
            reply, requests, tokens, failure = _generate_part(
                TLDR, prompts.TLDR_INSTRUCTION, prompts.build_tldr_prompt(verified), "tldr", emit)
        except _RunStopped as stop:
            if not facets:
                raise stop.error from None  # only the TL;DR was asked for
            stopped = stop
            reply, requests, tokens, failure = None, stop.requests, {}, None
        if stopped:
            tldr = Part(TLDR, "not_started", reason=stopped.error.reason, passages=cited, requests=requests,
                        until=stopped.until, **built)
        elif failure:
            tldr = Part(TLDR, "failed", reason=failure, passages=cited, requests=requests, tokens=tokens, **built)
        else:
            emit("progress", {"part": TLDR, "step": "checking"})
            tldr = _tldr_part(reply.text, verified, passages=cited, requests=requests, tokens=tokens, **built)
    if rewrite_tldr:
        emit("part", part_body(tldr))

    run_parts = [p for p in sections if p.part in facets] + ([tldr] if rewrite_tldr else [])
    summary = Summary(
        paper_id=paper_id,
        title=paper.title,
        arxiv_id=paper.arxiv_id,
        tldr=tldr,
        sections=sections,
        passages=sorted(seen.values(), key=lambda p: p.number),
        plan=plan,
        requests={k: sum(p.requests[k] for p in run_parts) for k in ("planned", "retries")},
        model=settings.llm_model,
        prompt_version=prompts.SUMMARY_PROMPT_VERSION,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    logger.info("Summarized %s: %d of 6 parts verified, %d requests", paper_id, summary.verified_parts,
                summary.requests["planned"])
    return summary


# --- Feature 4: comparisons (spec US3, research R4, ADR-0008) ---

COMPARE_PASSAGES = 3  # passages per paper per aspect (research R4)
MIN_PAPERS, MAX_PAPERS = 2, 4


@dataclass(frozen=True)
class ComparisonRow:
    """One aspect of a comparison: a failed row has no cells."""

    aspect: str
    state: str  # ok, failed, not_started
    reason: str | None = None
    cells: list[Part] = field(default_factory=list)
    requests: dict[str, int] = field(default_factory=lambda: {"planned": 0, "retries": 0})
    tokens: dict[str, int] = field(default_factory=dict)
    until: str | None = None  # not_started: when requests resume


@dataclass(frozen=True)
class Comparison:
    """A table of 2-4 papers and a set of aspects, with numbered passages (data-model.md)."""

    paper_ids: list[str]
    papers: list[dict]  # paper_id, title, arxiv_id, label
    aspects: list[str]
    rows: list[ComparisonRow]
    passages: list[NumberedPassage]
    plan: dict
    requests: dict[str, int]
    model: str
    prompt_version: int
    created_at: str
    status: str = "current"
    stale_reason: str | None = None
    pending: dict | None = None

    @property
    def total_cells(self) -> int:
        return len(self.papers) * len(self.rows)

    @property
    def verified_cells(self) -> int:
        return sum(1 for row in self.rows for cell in row.cells if cell.state == "verified")


def comparison_to_dict(comparison: Comparison) -> dict:
    return asdict(comparison)


def comparison_from_dict(data: dict) -> Comparison:
    """Rebuild a comparison saved with comparison_to_dict."""
    rows = [ComparisonRow(**{**row, "cells": [_part_from_dict(c) for c in row["cells"]]}) for row in data["rows"]]
    return Comparison(**{**data, "rows": rows, "passages": [NumberedPassage(**d) for d in data["passages"]]})


def _comparison_key(paper_ids: list[str], aspects: list[str], kind: str = "comparison") -> library.ResultKey:
    return library.result_key(kind, paper_ids, aspects)


def _ordered_aspects(aspects: list[str]) -> list[str]:
    unknown = [a for a in aspects if a not in prompts.ASPECTS]
    if unknown or not aspects:
        raise ValueError(f"Unknown or missing comparison aspects: {unknown or aspects}")
    return [a for a in prompts.ASPECTS if a in aspects]


def _check_papers(paper_ids: list[str]) -> list[library.PaperSummary]:
    if not MIN_PAPERS <= len(paper_ids) <= MAX_PAPERS or len(set(paper_ids)) != len(paper_ids):
        raise ValueError(f"A comparison needs {MIN_PAPERS} to {MAX_PAPERS} different papers")
    return [_paper(paper_id) for paper_id in paper_ids]


def comparison_plan(paper_ids: list[str], aspects: list[str], retry_aspects: list[str] | None = None) -> dict:
    """The most model requests a comparison (or a retry of some rows) can make (FR-021)."""
    parts = _ordered_aspects(retry_aspects if retry_aspects is not None else aspects)
    return {"max_requests": len(parts), "parts": parts}


def _rows_to_finish(comparison: Comparison) -> list[str]:
    return [row.aspect for row in comparison.rows if row.state in ("failed", "not_started")]


def _unfinished_comparison(paper_ids: list[str], aspects: list[str]) -> Comparison | None:
    settings = load_settings()
    found = library.load_result(_comparison_key(paper_ids, aspects, "comparison_unfinished"), settings.llm_model,
                                prompts.SUMMARY_PROMPT_VERSION)
    return comparison_from_dict(found[0]) if found and found[1] is None else None


def saved_comparison(paper_ids: list[str], aspects: list[str]) -> Comparison | None:
    """The saved comparison, current or stale, in any paper and aspect order; never generates."""
    settings = load_settings()
    aspects = _ordered_aspects(aspects)
    found = library.load_result(_comparison_key(paper_ids, aspects), settings.llm_model, prompts.SUMMARY_PROMPT_VERSION)
    if found is None:
        return None
    data, stale_reason = found
    comparison = comparison_from_dict(data)
    if stale_reason == "passages_changed":
        comparison = replace(comparison, passages=[replace(p, moved=_passage_moved(p)) for p in comparison.passages])
    unfinished = _unfinished_comparison(paper_ids, aspects)
    pending = {
        "created_at": unfinished.created_at,
        "failed_aspects": _rows_to_finish(unfinished),
        "retry_aspects": _rows_to_finish(unfinished),
        "verified_cells": unfinished.verified_cells,
    } if unfinished else None
    return replace(comparison, status="stale" if stale_reason else "current", stale_reason=stale_reason, pending=pending)


def _save_comparison(key: library.ResultKey, comparison: Comparison) -> None:
    library.save_result(key, comparison_to_dict(replace(comparison, pending=None)), comparison.model,
                        comparison.prompt_version)


def compare(
    paper_ids: list[str],
    aspects: list[str],
    regenerate: bool = False,
    retry_aspects: list[str] | None = None,
    on_event: Callable[[str, dict], None] | None = None,
) -> Comparison:
    """Compare 2-4 papers on some aspects: one request per aspect, the same number of passages per
    paper, each cell validated against its own paper's passages (FR-007-FR-010). Saved comparisons
    are reused in any order; a run with failed rows never replaces a complete one (FR-019, FR-020).

    `on_event(kind, detail)` receives "plan", "progress" ({part: aspect, step, passages?}),
    "retry_wait" ({part, ...}), "part" (a checked cell, named "<aspect>:<paper_id>") and "row_failed"
    ({aspect, reason}). A systemic model failure stops the run as for summaries (FR-024).
    Raises ValueError (bad input, or nothing to retry), UnknownPaperError, DailyLimitError (fewer
    requests left than the plan, nothing sent), or the stopping LLMError if nothing had finished.
    """
    papers = _check_papers(paper_ids)
    wanted = _ordered_aspects(aspects)
    base: Comparison | None = None
    unfinished: Comparison | None = None
    if retry_aspects is not None:
        retried = _ordered_aspects(retry_aspects)
        if set(retried) - set(wanted):
            raise ValueError(f"Rows to retry are not in this comparison: {retried}")
        unfinished = _unfinished_comparison(paper_ids, wanted)
        base = unfinished or saved_comparison(paper_ids, wanted)
        if base is None:
            raise ValueError("No saved comparison to retry rows of")
        if base.status == "stale":
            raise ValueError("The saved comparison is an earlier one; regenerate it in full")
    else:
        retried = wanted
        saved = saved_comparison(paper_ids, wanted)
        if saved is not None and not regenerate:
            return saved

    check_request_budget(len(retried))
    comparison = _run_comparison(papers, wanted, retried, base, on_event)
    key = _comparison_key(paper_ids, wanted)
    saved = saved_comparison(paper_ids, wanted)
    keep_saved = saved is not None and not _rows_to_finish(saved) and _rows_to_finish(comparison)
    if (unfinished is not None or retry_aspects is None) and keep_saved:
        logger.warning("Comparison ended with failed rows; kept the saved comparison")
        _save_comparison(_comparison_key(paper_ids, wanted, "comparison_unfinished"), comparison)
        return replace(saved_comparison(paper_ids, wanted), requests=comparison.requests)
    _save_comparison(key, comparison)
    library.delete_result(_comparison_key(paper_ids, wanted, "comparison_unfinished"))
    return comparison


def _run_comparison(
    papers: list[library.PaperSummary],
    wanted: list[str],
    retried: list[str],
    base: Comparison | None,
    on_event: Callable[[str, dict], None] | None,
) -> Comparison:
    """Generate the retried rows (the others come from `base`)."""

    def emit(kind: str, detail: dict) -> None:
        if on_event is not None:
            on_event(kind, detail)

    settings = load_settings()
    plan = comparison_plan([p.paper_id for p in papers], wanted, retried)
    emit("plan", plan)
    seen: dict[str, NumberedPassage] = {p.passage_id: p for p in base.passages} if base else {}
    kept = {row.aspect: row for row in base.rows} if base else {}
    labelled = base.papers if base else [
        {"paper_id": p.paper_id, "title": p.title, "arxiv_id": p.arxiv_id, "label": f"P{i}"}
        for i, p in enumerate(papers, start=1)
    ]
    rows: list[ComparisonRow] = []
    stopped: _RunStopped | None = None
    for aspect in wanted:
        if aspect not in retried:
            rows.append(kept[aspect])
        elif stopped:
            emit("row_failed", {"aspect": aspect, "reason": stopped.error.reason})
            rows.append(ComparisonRow(aspect, "not_started", reason=stopped.error.reason, until=stopped.until))
        else:
            try:
                rows.append(_run_row(aspect, labelled, seen, settings.relevance_threshold, emit))
            except _RunStopped as stop:
                if not any(row.aspect in retried for row in rows):
                    raise stop.error from None  # nothing finished, so nothing to keep
                stopped = stop
                emit("row_failed", {"aspect": aspect, "reason": stop.error.reason})
                rows.append(ComparisonRow(aspect, "not_started", reason=stop.error.reason, requests=stop.requests,
                                          until=stop.until))

    run_rows = [row for row in rows if row.aspect in retried]
    comparison = Comparison(
        paper_ids=[p["paper_id"] for p in labelled],
        papers=labelled,
        aspects=wanted,
        rows=rows,
        passages=sorted(seen.values(), key=lambda p: p.number),
        plan=plan,
        requests={k: sum(row.requests[k] for row in run_rows) for k in ("planned", "retries")},
        model=settings.llm_model,
        prompt_version=prompts.SUMMARY_PROMPT_VERSION,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    logger.info("Compared %d papers: %d of %d cells verified, %d requests", len(labelled), comparison.verified_cells,
                comparison.total_cells, comparison.requests["planned"])
    return comparison


def _run_row(
    aspect: str, labelled: list[dict], seen: dict[str, NumberedPassage], threshold: float, emit: Callable[[str, dict], None]
) -> ComparisonRow:
    """One aspect: retrieve per paper, one model request, then judge each cell on its own."""
    spec = prompts.ASPECTS[aspect]
    emit("progress", {"part": aspect, "step": "searching"})
    numbered: dict[str, list[NumberedPassage]] = {}
    for paper in labelled:
        retrieval = facet_retrieval(spec.facet, paper["paper_id"], k=COMPARE_PASSAGES)
        relevant = retrieval.passages and retrieval.gate_score is not None and retrieval.gate_score >= threshold
        numbered[paper["paper_id"]] = number_passages(retrieval.passages, seen) if relevant else []

    def cell_name(paper: dict) -> str:
        return f"{aspect}:{paper['paper_id']}"

    def not_retrieved(paper: dict) -> Part:
        return Part(cell_name(paper), "not_reported", reason="below_threshold")

    if not any(numbered.values()):
        cells = [not_retrieved(paper) for paper in labelled]
        for cell in cells:
            emit("part", part_body(cell))
        return ComparisonRow(aspect, "ok", cells=cells)

    emit("progress", {"part": aspect, "step": "reading", "passages": sum(len(p) for p in numbered.values())})
    emit("progress", {"part": aspect, "step": "generating"})
    prompt = prompts.build_row_prompt(aspect, [(p["label"], p["title"], numbered[p["paper_id"]]) for p in labelled])
    reply, requests, tokens, failure = _generate_part(aspect, prompts.ROW_INSTRUCTION, prompt, "comparison", emit)
    if failure:
        emit("row_failed", {"aspect": aspect, "reason": failure})
        return ComparisonRow(aspect, "failed", reason=failure, requests=requests, tokens=tokens)
    emit("progress", {"part": aspect, "step": "checking"})
    try:
        texts = prompts.parse_row(reply.text, [p["label"] for p in labelled])
    except RowFormatError:
        logger.warning("The comparison row %s was not valid JSON", aspect)
        emit("row_failed", {"aspect": aspect, "reason": "malformed"})
        return ComparisonRow(aspect, "failed", reason="malformed", requests=requests, tokens=tokens)

    cells = []
    for paper in labelled:
        numbers = [p.number for p in numbered[paper["paper_id"]]]
        if not numbers:
            cell = not_retrieved(paper)
        elif paper["label"] not in texts:
            cell = Part(cell_name(paper), "not_reported", reason="missing_cell", passages=numbers)
        else:
            cell = _section_part(cell_name(paper), texts[paper["label"]], set(numbers), passages=numbers)
        emit("part", part_body(cell))
        cells.append(cell)
    return ComparisonRow(aspect, "ok", cells=cells, requests=requests, tokens=tokens)
