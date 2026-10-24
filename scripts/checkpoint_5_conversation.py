"""Checkpoint 5: follow-up questions (SC-005) and the probe-question answers (FR-019, SC-006).

Calls the configured model and prints how many requests it used. It fails if it makes more
first attempts than planned for the selected parts, or if all requests including retries
exceed twice the plan (scripts/request_budget.py). The probe part writes eval/probe_answers.md for reviewer verdicts.

Usage: python scripts/checkpoint_5_conversation.py [conversation] [probe]   (default: all parts)
"""

import logging
import sys
import time
from datetime import date
from pathlib import Path

# Allow `python scripts/checkpoint_5_conversation.py` from the repo root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
# Print Unicode (−, ﬁ, Θ) on a Windows console without PYTHONIOENCODING.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from checkpoint_4_answer import WORD_LIMIT, budget, check, record, show, timing_summary  # noqa: E402

from paperpilot import library, llm, store  # noqa: E402
from paperpilot.config import load_settings  # noqa: E402
from paperpilot.errors import PaperPilotError  # noqa: E402
from paperpilot.service import Answer, Turn, ask  # noqa: E402

FIRST_QUESTION = "What is LoRA?"
# Each follow-up refers back to LoRA without naming it.
FOLLOW_UPS = [
    "What are its limitations?",
    "How does that method reduce the number of trainable parameters?",
]
REFERENT = "lora"
# The five baseline questions of eval/probe_notes.md. Q2 and Q4 have their answer passages
# outside the top 6, so not-found or a limited partial answer is the correct outcome.
PROBE_QUESTIONS = [
    ("Q1", "Which dataset was the Transformer trained on for English-German translation?", None),
    ("Q2", "What are the two pre-training tasks of BERT?", "answer passages rank 13 and 25"),
    ("Q3", "How many retrieved documents does RAG use at test time?", None),
    ("Q4", "What rank r does LoRA use for GPT-3?", "answer passage ranks 18"),
    ("Q5", "Where in the context do models use information best?", None),
]
PROBE_REPORT = ROOT / "eval" / "probe_answers.md"
PARTS = ("conversation", "probe")
# Planned model calls per part (first attempts): the first question, then a rewrite and an
# answer per follow-up; one answer per probe question. Retries are counted separately.
PART_PLANS = {"conversation": 1 + 2 * len(FOLLOW_UPS), "probe": len(PROBE_QUESTIONS)}


def _cell(text: str) -> str:
    """Make text safe for one Markdown table cell."""
    return " ".join(str(text).split()).replace("|", "\\|")


def write_probe_report(rows: list[tuple[str, str, Answer, int]], model: str, threshold: float) -> None:
    """Write eval/probe_answers.md: one section per probe question with an empty verdict."""
    lines = [
        "# Probe answers",
        "",
        f"Date: {date.today().isoformat()}. Model: `{model}`. Threshold: {threshold} (top-score gate). "
        "Written by `scripts/checkpoint_5_conversation.py`; fill in the reviewer verdicts by hand.",
        "",
        "| # | Question | Not found | Valid | Invalid | Words | Requests | Reviewer verdict |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for label, question, answer, used in rows:
        c = answer.citations
        lines.append(f"| {label} | {_cell(question)} | {'yes' if answer.not_found else 'no'} | {c.valid} | "
                     f"{c.invalid} | {answer.word_count} | {used} |  |")
    for label, question, answer, used in rows:
        c = answer.citations
        lines += [
            "",
            f"## {label}. {question}",
            "",
            f"**Answer** ({answer.word_count} words): {answer.text}",
            "",
            f"- Citations: valid {c.valid}, invalid {c.invalid}; uncited sentences: {len(c.uncited_sentences)}",
            f"- Warning: {answer.warning}",
            f"- Fallback reason: {answer.fallback_reason}",
            f"- LLM requests: {used}",
            "",
            "| [n] | Paper | Section | Page | Score |",
            "|---|---|---|---|---|",
        ]
        lines += [f"| {p.number} | {_cell(p.title)} | {_cell(p.section)} | {p.page} | {p.score:.3f} |"
                  for p in answer.passages]
        lines += ["", "**Reviewer verdict**: "]
    PROBE_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    """Run the conversation and the probe questions; return 0 if every check passes."""
    logging.basicConfig(level=logging.WARNING)
    parts = [a.lower() for a in sys.argv[1:]] or list(PARTS)
    unknown = [p for p in parts if p not in PARTS]
    if unknown:
        print(f"Unknown part(s) {unknown}; choose from {', '.join(PARTS)} (default: all)")
        return 2
    settings = load_settings()
    print("Checkpoint 5: conversation and probe answers")
    print(f"Provider: {settings.llm_provider}   Model: {settings.llm_model}   "
          f"Threshold: {settings.relevance_threshold}")
    start = time.perf_counter()
    store.load_model()
    library.search(FIRST_QUESTION)
    print(f"Cold: model load + library open + first search {time.perf_counter() - start:.1f} s")
    results: list[tuple[bool, str]] = []
    llm.reset_request_count()

    try:
        if "conversation" in parts:
            print(f"\n=== First question: {FIRST_QUESTION}")
            first = record(ask(FIRST_QUESTION))
            show(first)
            history = [Turn("user", FIRST_QUESTION), Turn("assistant", first.text)]

            for question in FOLLOW_UPS:
                before = llm.request_counts()
                print(f"\n=== Follow-up: {question}")
                answer = record(ask(question, history=history))
                print(f"Original question:   {answer.question}")
                print(f"Standalone question: {answer.standalone_question}")
                print(f"Rewrite applied: {answer.rewrite_applied}   "
                      f"rewrite_fallback_reason: {answer.rewrite_fallback_reason}")
                show(answer)
                used = llm.request_counts() - before
                print(f"LLM requests for this follow-up: {used.total} ({used.planned} planned, "
                      f"{used.retries} retries)")
                check(results, answer.rewrite_applied, "the follow-up was rewritten")
                check(results, REFERENT in answer.standalone_question.lower(),
                      "the standalone question names LoRA (SC-005)")
                check(results, not answer.citations.invalid, "every citation maps to a provided passage")
                history += [Turn("user", question), Turn("assistant", answer.text)]

        if "probe" in parts:
            rows: list[tuple[str, str, Answer, int]] = []
            for label, question, low_rank_note in PROBE_QUESTIONS:
                before = llm.request_count()
                print(f"\n=== Probe {label}: {question}")
                answer = record(ask(question))
                show(answer)
                used = llm.request_count() - before
                rows.append((label, question, answer, used))
                check(results, not answer.citations.invalid, f"{label}: no invalid citation returned")
                level = "INFO" if answer.word_count <= WORD_LIMIT else "WARN"
                print(f"{level}: {label} answer length {answer.word_count} words (limit {WORD_LIMIT}, reported only)")
                if low_rank_note:
                    print(f"INFO: {label} — {low_rank_note}, outside the top 6; not-found or a limited "
                          "partial answer is the correct outcome")
            write_probe_report(rows, settings.llm_model, settings.relevance_threshold)
            print(f"\nWrote {PROBE_REPORT.relative_to(ROOT)} (reviewer verdicts to fill in)")
    except PaperPilotError as error:
        check(results, False, f"{type(error).__name__}: {error}")

    print()
    timing_summary(results)
    used = llm.request_counts()
    plan = sum(PART_PLANS[part] for part in parts)
    print(f"\nLLM requests: {used.total} ({used.planned} planned, {used.retries} retries; plan {plan})")
    budget(results, "checkpoint 5", used, plan)
    all_passed = all(passed for passed, _ in results)
    print(f"\n{'PASS' if all_passed else 'FAIL'}: checkpoint 5 automated checks")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
