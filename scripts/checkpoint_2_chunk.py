"""Checkpoint 2: passages cover the paper, text passages are well sized and read on their own (SC-003).

Usage: python scripts/checkpoint_2_chunk.py <papers_dir>
"""

import random
import sys
import time
from pathlib import Path

# Allow `python scripts/checkpoint_2_chunk.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Print Unicode (−, ﬁ, Θ) on a Windows console without PYTHONIOENCODING.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from paperpilot.config import load_settings  # noqa: E402
from paperpilot.errors import PaperPilotError  # noqa: E402
from paperpilot.ingest import Passage, chunk_sections, parse_pdf  # noqa: E402

MIN_COVERAGE = 0.97
TEXT_AVERAGE_RANGE = (150, 230)
SAMPLES = 3
SEED = 0
HEAD_CHARS, TAIL_CHARS = 500, 150


def preview(text: str) -> str:
    """Return the start and end of a passage, enough to judge whether it reads on its own."""
    if len(text) <= HEAD_CHARS + TAIL_CHARS:
        return text
    return f"{text[:HEAD_CHARS]} … {text[-TAIL_CHARS:]}"


def show(passage: Passage) -> None:
    """Print one passage with its location for human review."""
    print(
        f"\n  [{passage.passage_id}] {passage.kind}, section: {passage.section}, page {passage.page}, "
        f"{passage.word_count} words"
    )
    print(f"  {preview(passage.text)}")


def new_word_count(passages: list[Passage], overlap: int) -> int:
    """Count passage words, excluding overlap repeated from the previous passage of a section."""
    total = 0
    for previous, current in zip([None, *passages[:-1]], passages):
        words, shared = current.text.split(), 0
        if previous is not None and previous.section == current.section:
            previous_words = previous.text.split()
            for k in range(min(overlap, len(previous_words), len(words)), 0, -1):
                if previous_words[-k:] == words[:k]:
                    shared = k
                    break
        total += len(words) - shared
    return total


def main() -> int:
    """Chunk every PDF in the folder, print stats, samples and PASS/FAIL lines; 0 if all pass."""
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    papers = sorted(Path(sys.argv[1]).glob("*.pdf"))
    if not papers:
        print(f"FAIL: no PDFs found in {sys.argv[1]}")
        return 1

    settings = load_settings()
    low, high = TEXT_AVERAGE_RANGE
    print("Checkpoint 2: chunking")
    print(
        f"Settings: CHUNK_WORDS={settings.chunk_words} CHUNK_OVERLAP={settings.chunk_overlap} "
        f"MIN_CHUNK_WORDS={settings.min_chunk_words}"
    )
    rng = random.Random(SEED)
    all_passed, timings = True, []
    for path in papers:
        print(f"\n=== {path.name}")
        try:
            paper = parse_pdf(path)
        except PaperPilotError as error:
            print(f"FAIL: {error}")
            all_passed = False
            continue
        start = time.perf_counter()
        passages = chunk_sections(paper.sections, paper.paper_id, paper.title, settings)
        timings.append((path.name, time.perf_counter() - start))

        counts = [p.word_count for p in passages]
        average = sum(counts) / len(counts) if counts else 0.0
        body_words = sum(len(b.text.split()) for s in paper.sections for b in s.blocks)
        coverage = new_word_count(passages, settings.chunk_overlap) / body_words
        text_passages = [p for p in passages if p.kind == "text"]
        table_passages = [p for p in passages if p.kind == "table"]
        text_average = sum(p.word_count for p in text_passages) / len(text_passages) if text_passages else 0.0
        print(f"Title: {paper.title}")
        print(
            f"Passages: {len(passages)} ({len(text_passages)} text, {len(table_passages)} table)   "
            f"words: average {average:.0f} (text only {text_average:.0f}), "
            f"min {min(counts, default=0)}, max {max(counts, default=0)}   body words: {body_words}"
        )
        checks = [
            (coverage >= MIN_COVERAGE, f"passages cover {coverage:.1%} of body words (need {MIN_COVERAGE:.0%})"),
            (low <= text_average <= high, f"text passages average {low}-{high} words"),
        ]
        for passed, description in checks:
            print(f"{'PASS' if passed else 'FAIL'}: {description}")
            all_passed = all_passed and passed

        print("\n  Text samples (readability review):")
        for passage in rng.sample(text_passages, min(SAMPLES, len(text_passages))):
            show(passage)
        if table_passages:
            print("\n  Table sample:")
            show(rng.choice(table_passages))
        else:
            print("\n  Table sample: none (no table passages)")

    print("\nChunk timings:")
    for name, seconds in timings:
        print(f"  {name}: {seconds * 1000:.1f} ms")
    print(f"\n{'PASS' if all_passed else 'FAIL'}: checkpoint 2 automated checks")
    print("Review the samples above: each should read sensibly on its own (SC-003: 9 of 10).")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
