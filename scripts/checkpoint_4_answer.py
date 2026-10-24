"""Checkpoint 4: grounded answers with valid citations (SC-001, SC-010, SC-011).

Calls the configured model (OpenRouter free tier by default) and prints how many requests
it used; it stops with FAIL if it exceeds its request budget.

Usage: python scripts/checkpoint_4_answer.py [us1] [us2] [nearmiss]   (default: all parts)
"""

import logging
import statistics
import sys
import time
from pathlib import Path

# Allow `python scripts/checkpoint_4_answer.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from paperpilot import library, llm, prompts, store  # noqa: E402
from paperpilot.config import load_settings  # noqa: E402
from paperpilot.errors import PaperPilotError  # noqa: E402
from paperpilot.service import Answer, ask  # noqa: E402

REQUEST_BUDGET = 6
WORD_LIMIT = 165  # 150 + 10% margin (SC-011); reported, never enforced
MEDIAN_GENERATE_LIMIT = 15.0  # SC-008: median generate time of answered questions
# Its top passage (Attention, Introduction) contains the paper's own markers such as "[13]".
US1_QUESTION = "What recurrent models were state of the art for sequence modelling before the Transformer?"
US2_QUESTION = "What is the capital of France?"
# Topic-level near-misses: in-domain but not answered by the test papers. They pass the
# threshold (research R8), so the model's not-found rule must catch them.
NEARMISS_QUESTIONS = [
    "How was GPT-4 trained?",
    "What is the context window of Claude 3?",  # the papers only cover Claude-1.3
    "How does Llama 2 handle safety tuning?",
]
NEARMISS_BUDGET = 3
PARTS = ("us1", "us2", "nearmiss")
PREVIEW_CHARS = 160


ANSWERS: list[Answer] = []  # every answer in this run, for the SC-008 timing summary


def record(answer: Answer) -> Answer:
    """Keep an answer for the timing summary and return it."""
    ANSWERS.append(answer)
    return answer


def timing_summary(results: list[tuple[bool, str]]) -> None:
    """SC-008: check the median generate time of answered questions; report the rest."""
    answered = [a.timings["generate"] for a in ANSWERS if not a.not_found]
    refused = [a.timings["generate"] for a in ANSWERS if a.not_found and a.llm_calls]
    if refused:
        print(f"INFO: not-found generate times {', '.join(f'{t:.1f} s' for t in refused)} (reported only)")
    if not answered:
        print("INFO: no answered questions in this run; SC-008 median not checked")
        return
    print(f"INFO: maximum generate time {max(answered + refused):.1f} s (reported only)")
    median = statistics.median(answered)
    check(results, median <= MEDIAN_GENERATE_LIMIT,
          f"median generate time of {len(answered)} answered question(s) is {median:.1f} s "
          f"(limit {MEDIAN_GENERATE_LIMIT:.0f} s, SC-008)")


def show(answer: Answer) -> None:
    """Print an answer with its passages, citation check, fallback reason, timings and tokens."""
    print(f"\nAnswer ({answer.word_count} words):\n  {answer.text}")
    print("\nPassages:")
    for p in answer.passages:
        print(f"  [{p.number}] {p.score:.3f}  {p.title} — {p.section}, p. {p.page}")
        print(f"      {p.text[:PREVIEW_CHARS]}…")
    c = answer.citations
    print(f"\nCitations: valid {c.valid}, invalid {c.invalid}")
    for sentence in c.uncited_sentences:
        print(f"  uncited sentence: {sentence}")
    print(f"Warning: {answer.warning}")
    print(f"Fallback reason: {answer.fallback_reason}")
    t = answer.timings
    print(f"Timings: rewrite {t['rewrite']:.2f} s, retrieve {t['retrieve']:.2f} s, generate {t['generate']:.2f} s")
    print(f"Tokens: {answer.tokens or 'not reported'}   LLM calls in this answer: {answer.llm_calls}")


def check(results: list[tuple[bool, str]], passed: bool, description: str) -> None:
    """Print and record one PASS/FAIL line."""
    print(f"{'PASS' if passed else 'FAIL'}: {description}")
    results.append((passed, description))


def main() -> int:
    """Run the checkpoint; return 0 if every check passes."""
    logging.basicConfig(level=logging.WARNING)
    parts = [a.lower() for a in sys.argv[1:]] or list(PARTS)
    unknown = [p for p in parts if p not in PARTS]
    if unknown:
        print(f"Unknown part(s) {unknown}; choose from {', '.join(PARTS)} (default: all)")
        return 2
    settings = load_settings()
    print("Checkpoint 4: grounded answers")
    print(f"Provider: {settings.llm_provider}   Model: {settings.llm_model}   "
          f"Threshold: {settings.relevance_threshold}")
    results: list[tuple[bool, str]] = []
    llm.reset_request_count()

    # One-time startup costs, reported separately so answer timings show per-question cost:
    # importing and loading the embedding model, then opening the library and its first search.
    start = time.perf_counter()
    store.load_model()
    print(f"Cold: embedding model import + load {time.perf_counter() - start:.1f} s")
    start = time.perf_counter()
    library.search(US1_QUESTION)
    print(f"Cold: library open + first search {time.perf_counter() - start:.2f} s (excluded from answer timings)")

    try:
        check(results, llm.model_is_listed(), f"model {settings.llm_model} is listed by the provider")

        if "us1" in parts:
            print(f"\n=== US1: {US1_QUESTION}")
            answer = record(ask(US1_QUESTION))
            show(answer)
            markers = sum(1 for p in answer.passages if prompts.strip_reference_markers(p.text) != p.text)
            print(f"\nINFO: {markers} of {len(answer.passages)} passages contained the papers' own reference "
                  "markers; they were removed from the prompt")
            check(results, bool(answer.citations.valid), "the answer has at least one citation")
            check(results, not answer.citations.invalid, "every citation maps to a provided passage")
            level = "INFO" if answer.word_count <= WORD_LIMIT else "WARN"
            print(f"{level}: answer length {answer.word_count} words (limit {WORD_LIMIT}, reported only)")

        if "us2" in parts:
            print(f"\n=== US2: {US2_QUESTION}")
            before = llm.request_count()
            answer = record(ask(US2_QUESTION))
            show(answer)
            check(results, answer.text == prompts.NOT_FOUND, "the answer is exactly the not-found sentence")
            check(results, llm.request_count() == before, "no LLM request was made (rejected by the threshold)")

        if "nearmiss" in parts:
            before = llm.request_count()
            for question in NEARMISS_QUESTIONS:
                print(f"\n=== Near-miss: {question}")
                answer = record(ask(question))
                show(answer)
                if answer.not_found:
                    check(results, True, f"not-found ({answer.fallback_reason}) for: {question}")
                    continue
                print(f"WARN: the model gave a cited answer for: {question} — judge whether these "
                      "cited passages really support it:")
                for p in answer.passages:
                    if p.number in answer.citations.valid:
                        print(f"\n  [{p.number}] {p.title} — {p.section}, p. {p.page}\n  {p.text}")
            used = llm.request_count() - before
            check(results, used <= NEARMISS_BUDGET, f"near-miss part used {used} LLM requests (budget {NEARMISS_BUDGET})")
    except PaperPilotError as error:
        check(results, False, f"{type(error).__name__}: {error}")

    print()
    timing_summary(results)
    used = llm.request_count()
    print(f"\nLLM requests: {used} (budget {REQUEST_BUDGET})")
    check(results, used <= REQUEST_BUDGET, "stayed within the request budget")
    all_passed = all(passed for passed, _ in results)
    print(f"\n{'PASS' if all_passed else 'FAIL'}: checkpoint 4 automated checks")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
