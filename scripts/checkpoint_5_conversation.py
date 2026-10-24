"""Checkpoint 5: follow-up questions are rewritten from the conversation (SC-005).

Calls the configured model and prints how many requests it used; it stops with FAIL if it
exceeds its request budget.

Usage: python scripts/checkpoint_5_conversation.py
"""

import logging
import sys
import time
from pathlib import Path

# Allow `python scripts/checkpoint_5_conversation.py` from the repo root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
# Print Unicode (−, ﬁ, Θ) on a Windows console without PYTHONIOENCODING.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from checkpoint_4_answer import check, record, show, timing_summary  # noqa: E402

from paperpilot import library, llm, store  # noqa: E402
from paperpilot.config import load_settings  # noqa: E402
from paperpilot.errors import PaperPilotError  # noqa: E402
from paperpilot.service import Turn, ask  # noqa: E402

REQUEST_BUDGET = 12
FIRST_QUESTION = "What is LoRA?"
# Each follow-up refers back to LoRA without naming it.
FOLLOW_UPS = [
    "What are its limitations?",
    "How does that method reduce the number of trainable parameters?",
]
REFERENT = "lora"


def main() -> int:
    """Run the conversation; return 0 if every check passes."""
    logging.basicConfig(level=logging.WARNING)
    settings = load_settings()
    print("Checkpoint 5: conversation")
    print(f"Provider: {settings.llm_provider}   Model: {settings.llm_model}   "
          f"Threshold: {settings.relevance_threshold}")
    start = time.perf_counter()
    store.load_model()
    library.search(FIRST_QUESTION)
    print(f"Cold: model load + library open + first search {time.perf_counter() - start:.1f} s")
    results: list[tuple[bool, str]] = []
    llm.reset_request_count()

    try:
        print(f"\n=== First question: {FIRST_QUESTION}")
        first = record(ask(FIRST_QUESTION))
        show(first)
        history = [Turn("user", FIRST_QUESTION), Turn("assistant", first.text)]

        for question in FOLLOW_UPS:
            before = llm.request_count()
            print(f"\n=== Follow-up: {question}")
            answer = record(ask(question, history=history))
            print(f"Original question:   {answer.question}")
            print(f"Standalone question: {answer.standalone_question}")
            print(f"Rewrite applied: {answer.rewrite_applied}   "
                  f"rewrite_fallback_reason: {answer.rewrite_fallback_reason}")
            show(answer)
            print(f"LLM requests for this follow-up: {llm.request_count() - before}")
            check(results, answer.rewrite_applied, "the follow-up was rewritten")
            check(results, REFERENT in answer.standalone_question.lower(),
                  "the standalone question names LoRA (SC-005)")
            check(results, not answer.citations.invalid, "every citation maps to a provided passage")
            history += [Turn("user", question), Turn("assistant", answer.text)]
    except PaperPilotError as error:
        check(results, False, f"{type(error).__name__}: {error}")

    print()
    timing_summary(results)
    used = llm.request_count()
    print(f"\nLLM requests: {used} (budget {REQUEST_BUDGET})")
    check(results, used <= REQUEST_BUDGET, "stayed within the request budget")
    all_passed = all(passed for passed, _ in results)
    print(f"\n{'PASS' if all_passed else 'FAIL'}: checkpoint 5 automated checks")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
