"""Calibrate RELEVANCE_THRESHOLD from search scores (FR-003, SC-003, research R8). No LLM requests.

Searches the library for on-topic and off-topic question groups, suggests a threshold just
below the lowest on-topic top score, and writes eval/threshold_calibration.md. The value is
calibrated for bge-small-en-v1.5 on this library; recalibrate when the model, chunking or
papers change.

Usage: python scripts/calibrate_threshold.py
"""

import math
import sys
from datetime import date
from pathlib import Path

# Allow `python scripts/calibrate_threshold.py` from the repo root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Print Unicode (−, ﬁ, Θ) on a Windows console without PYTHONIOENCODING.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from paperpilot import llm, store  # noqa: E402
from paperpilot.config import load_settings  # noqa: E402
from paperpilot.library import list_papers, search  # noqa: E402

MARGIN = 0.03
REPORT = ROOT / "eval" / "threshold_calibration.md"

GROUPS: dict[str, list[str]] = {
    "on-topic": [
        # The five probe questions (eval/probe_notes.md) ...
        "Which dataset was the Transformer trained on for English-German translation?",
        "What are the two pre-training tasks of BERT?",
        "How many retrieved documents does RAG use at test time?",
        "What rank r does LoRA use for GPT-3?",
        "Where in the context do models use information best?",
        # ... plus vague questions, which score lowest.
        "what dataset was used for evaluation?",
        "What are the limitations?",
        # Short definitional question; a false not-found in checkpoint 5 (research R8).
        "What is LoRA?",
        # Answered by Lost in the Middle p. 5 (Claude-1.3: 8K; Claude-1.3 (100K): 100K tokens).
        "What is the context window of Claude?",
    ],
    "clear off-topic": [
        "What is the capital of France?",
        "How do I bake a chocolate cake?",
        "Who won the 2018 FIFA World Cup?",
        "How do I change a flat tire on a car?",
        "What is the boiling point of water at sea level?",
        "Recommend a good movie for tonight",
    ],
    # Reuse the papers' words in another sense.
    "word-level near-miss": [
        "How do electrical transformers step down voltage?",
        "Who invented the BERT muppet character?",
        "What is the attention span of a goldfish?",
    ],
    # In-domain, but not answered by these five papers.
    "topic-level near-miss": [
        "How was GPT-4 trained?",
        "What is the context window of Claude 3?",
        "How does Llama 2 handle safety tuning?",
    ],
}


def main() -> int:
    """Measure top scores per group, suggest a threshold and write the report; 0 on success."""
    settings = load_settings()
    llm.reset_request_count()
    store.load_model()
    papers = list_papers()
    configured = settings.relevance_threshold

    top: dict[str, list[tuple[str, float]]] = {}
    for group, questions in GROUPS.items():
        top[group] = [(q, search(q, k=1)[0].score) for q in questions]

    lowest_on = min(score for _, score in top["on-topic"])
    suggested = math.floor((lowest_on - MARGIN) * 100) / 100
    highest_off = {g: max(s for _, s in rows) for g, rows in top.items() if g != "on-topic"}

    lines = [
        "# Relevance threshold calibration",
        "",
        f"Date: {date.today().isoformat()}. Library: {len(papers)} papers in `{settings.library_dir}`. "
        f"Embedding model: `{settings.embed_model}`. Chunking: {settings.chunk_words}/{settings.chunk_overlap}.",
        "",
        "Calibrated **for bge-small-en-v1.5 on this library**; recalibrate when the embedding model, "
        "chunking or papers change. Score = top-1 similarity (0–1).",
        "",
        f"| Group | Question | Top score | Rejected at {configured:.2f} | Rejected at {suggested:.2f} |",
        "|---|---|---|---|---|",
    ]
    for group, rows in top.items():
        for question, score in rows:
            lines.append(
                f"| {group} | {question} | {score:.3f} | {'yes' if score < configured else 'no'} | "
                f"{'yes' if score < suggested else 'no'} |"
            )
    lines += ["", "| Group | Questions | Min top | Max top | Rejected at configured | Rejected at suggested |",
              "|---|---|---|---|---|---|"]
    for group, rows in top.items():
        scores = [s for _, s in rows]
        rej_c = sum(s < configured for s in scores)
        rej_s = sum(s < suggested for s in scores)
        lines.append(f"| {group} | {len(scores)} | {min(scores):.3f} | {max(scores):.3f} | "
                     f"{rej_c}/{len(scores)} | {rej_s}/{len(scores)} |")
    lines += [
        "",
        f"- Lowest on-topic top score: **{lowest_on:.3f}**; suggested threshold = that − {MARGIN} rounded down "
        f"= **{suggested:.2f}** (configured: {configured:.2f}).",
        f"- Margin below the lowest on-topic question: {lowest_on - suggested:.3f}.",
    ]
    for group, value in highest_off.items():
        lines.append(f"- Margin above the highest {group} question: {suggested - value:+.3f} (max {value:.3f}).")
    lines += [
        "- On-topic questions are never rejected (clarification Q2). Topic-level near-misses are expected to "
        "pass the threshold; the model's not-found rule and citation checks are the second line of defence.",
        "",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    if abs(suggested - configured) > 0.02:
        print(f"WARN: suggested {suggested:.2f} differs from the configured {configured:.2f} by more than 0.02")
    on_rejected = sum(s < configured for _, s in top["on-topic"])
    print(f"{'PASS' if on_rejected == 0 else 'FAIL'}: no on-topic question rejected at the configured threshold")
    print(f"Wrote {REPORT.relative_to(ROOT)}")
    print(f"LLM requests: {llm.request_count()} (plan 0)")
    return 0 if on_rejected == 0 and llm.request_count() == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
