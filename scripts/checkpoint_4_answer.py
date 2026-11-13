"""Checkpoint 4: grounded answers with valid citations (SC-001, SC-010, SC-011).

Calls the configured model (OpenRouter free tier by default) and prints how many requests
it used. It fails if it makes more first attempts than planned for the selected parts, or if
all requests including retries exceed twice the plan (scripts/request_budget.py).

Usage: python scripts/checkpoint_4_answer.py [us1] [us2] [us3] [us5] [nearmiss] [secrets]   (default: all parts)
"""

import logging
import statistics
import subprocess
import sys
import time
from pathlib import Path

# Allow `python scripts/checkpoint_4_answer.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Print Unicode (−, ﬁ, Θ) on a Windows console without PYTHONIOENCODING.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from paperpilot import library, llm, prompts, store  # noqa: E402
from paperpilot.config import load_settings  # noqa: E402
from paperpilot.errors import PaperPilotError  # noqa: E402
from paperpilot.service import Answer, ask, review_reply  # noqa: E402
from request_budget import budget_checks  # noqa: E402

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
# (question, must get a cited answer). The tasks question is a known false not-found: its
# answer passages rank 13 and 22 within BERT (eval/probe_notes.md), outside the top 6.
US3_QUESTIONS = [
    ("What are the two pre-training tasks of BERT?", False),
    ("What data was BERT pre-trained on?", True),
]
US3_PAPER_TITLE_PREFIX = "BERT:"
# Crafted replies for the offline citation check (no LLM request): 6 passages provided.
US5_PASSAGES = 6
US5_INVALID = "The Transformer was trained on WMT 2014 English-German [2]. It used 8 P100 GPUs [9]."
US5_UNCITED = "The Transformer was trained on WMT 2014 English-German. It used 8 P100 GPUs."
PARTS = ("us1", "us2", "us3", "us5", "nearmiss", "secrets")
# Planned model calls per part (first attempts; retries are counted separately).
PART_PLANS = {"us1": 1, "us2": 0, "us3": len(US3_QUESTIONS), "us5": 0,
              "nearmiss": len(NEARMISS_QUESTIONS), "secrets": 0}
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


def budget(results: list[tuple[bool, str]], label: str, used: llm.RequestCounts, plan: int) -> None:
    """Check planned requests against the plan and all requests against the safety cap."""
    for passed, description in budget_checks(label, used, plan):
        check(results, passed, description)


def check_secrets(results: list[tuple[bool, str]], api_key: str) -> None:
    """SC-007: the key is in no tracked or untracked file except .env, describe() hides it and
    .env is ignored by git. Prints only PASS/FAIL lines, never the key."""
    root = Path(__file__).resolve().parents[1]
    if not api_key:
        check(results, False, "LLM_API_KEY is set, so the repository can be searched for it")
        return
    # Exit code 1 means no match; -e keeps a key starting with "-" from being read as an option.
    found = subprocess.run(
        ["git", "grep", "--untracked", "-F", "-q", "-e", api_key, "--", ".", ":!.env"],
        cwd=root, capture_output=True,
    ).returncode
    check(results, found == 1, "the API key appears in no tracked or untracked file except .env")
    settings = load_settings()
    hidden = api_key not in settings.describe() and api_key not in repr(settings)
    check(results, hidden and "LLM_API_KEY = set (hidden)" in settings.describe(),
          "describe() and repr() hide the API key")
    ignored = subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=root, capture_output=True).returncode
    check(results, ignored == 0, ".env is ignored by git")


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

        if "us3" in parts:
            bert = [p for p in library.list_papers() if p.title.startswith(US3_PAPER_TITLE_PREFIX)]
            if not bert:
                check(results, False, f"a paper titled '{US3_PAPER_TITLE_PREFIX}…' is in the library")
            else:
                paper = bert[0]
                for question, must_answer in US3_QUESTIONS:
                    print(f"\n=== US3: {question}  (filtered to {paper.paper_id}: {paper.title})")
                    answer = record(ask(question, paper_ids=[paper.paper_id]))
                    show(answer)
                    papers_used = sorted({p.title for p in answer.passages})
                    print(f"\nPapers of the passages used: {papers_used or 'none'}")
                    check(results, all(p.paper_id == paper.paper_id for p in answer.passages),
                          "every passage comes from the selected paper (SC-004)")
                    check(results, not answer.citations.invalid, "every citation maps to a provided passage")
                    if must_answer:
                        check(results, not answer.not_found and bool(answer.citations.valid),
                              "a cited answer came back through the filter")
                    elif answer.not_found:
                        print("INFO: known false not-found (answer passages rank 13 and 22 within BERT; "
                              "see eval/probe_notes.md)")

        if "us5" in parts:
            print(f"\n=== US5: offline citation check ({US5_PASSAGES} passages, no LLM request)")
            before = llm.request_count()
            for label, reply, reason, problem in (
                ("invalid citation", US5_INVALID, "invalid_citations", "[9]"),
                ("no citations", US5_UNCITED, "no_citations", "no citations"),
            ):
                text, citations, warning, rejected, fallback = review_reply(reply, US5_PASSAGES)
                print(f"\nReply ({label}): {reply}")
                print(f"  -> answer: {text}")
                print(f"  -> citations: valid {citations.valid}, invalid {citations.invalid}")
                print(f"  -> warning: {warning}")
                print(f"  -> fallback reason: {fallback}")
                check(results, text == prompts.NOT_FOUND and fallback == reason and rejected == reply,
                      f"{label}: replaced by the not-found sentence ({reason}), original kept")
                check(results, warning is not None and problem in warning.lower(),
                      f"{label}: the warning names the problem ({problem})")
            check(results, llm.request_count() == before, "the citation check made no LLM request")

        if "nearmiss" in parts:
            before = llm.request_counts()
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
            budget(results, "near-miss part", llm.request_counts() - before, PART_PLANS["nearmiss"])

        if "secrets" in parts:
            print("\n=== Secrets (no LLM request)")
            check_secrets(results, settings.llm_api_key)
    except PaperPilotError as error:
        check(results, False, f"{type(error).__name__}: {error}")

    print()
    timing_summary(results)
    used = llm.request_counts()
    plan = sum(PART_PLANS[part] for part in parts)
    print(f"\nLLM requests: {used.total} ({used.planned} planned, {used.retries} retries; plan {plan})")
    budget(results, "checkpoint 4", used, plan)
    all_passed = all(passed for passed, _ in results)
    print(f"\n{'PASS' if all_passed else 'FAIL'}: checkpoint 4 automated checks")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
