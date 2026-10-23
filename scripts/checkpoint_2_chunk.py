"""Checkpoint 2: passage counts and sizes look right and passages read on their own (SC-003).

Usage: python scripts/checkpoint_2_chunk.py <papers_dir>
"""

import random
import sys
import time
from pathlib import Path

# Allow `python scripts/checkpoint_2_chunk.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from paperpilot.config import load_settings  # noqa: E402
from paperpilot.errors import PaperPilotError  # noqa: E402
from paperpilot.ingest import Passage, chunk_sections, parse_pdf  # noqa: E402

MIN_COVERAGE = 0.97
COUNT_TOLERANCE = 0.25
TARGET_AVERAGE, AVERAGE_TOLERANCE = 200, 0.15
SAMPLES = 3
SEED = 0
HEAD_CHARS, TAIL_CHARS = 500, 150


def preview(text: str) -> str:
    """Return the start and end of a passage, enough to judge whether it reads on its own."""
    if len(text) <= HEAD_CHARS + TAIL_CHARS:
        return text
    return f"{text[:HEAD_CHARS]} … {text[-TAIL_CHARS:]}"


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
    low, high = TARGET_AVERAGE * (1 - AVERAGE_TOLERANCE), TARGET_AVERAGE * (1 + AVERAGE_TOLERANCE)
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
        expected = body_words / (settings.chunk_words - settings.chunk_overlap)
        print(f"Title: {paper.title}")
        print(
            f"Passages: {len(passages)}   words: average {average:.0f}, "
            f"min {min(counts, default=0)}, max {max(counts, default=0)}   body words: {body_words}"
        )
        checks = [
            (coverage >= MIN_COVERAGE, f"passages cover {coverage:.1%} of body words (need {MIN_COVERAGE:.0%})"),
            (
                abs(len(passages) - expected) <= COUNT_TOLERANCE * expected,
                f"passage count within ±25% of {expected:.0f} "
                f"({expected * (1 - COUNT_TOLERANCE):.0f}-{expected * (1 + COUNT_TOLERANCE):.0f})",
            ),
            (low <= average <= high, f"average words within ±15% of {TARGET_AVERAGE} ({low:.0f}-{high:.0f})"),
        ]
        for passed, description in checks:
            print(f"{'PASS' if passed else 'FAIL'}: {description}")
            all_passed = all_passed and passed

        for passage in rng.sample(passages, min(SAMPLES, len(passages))):
            print(
                f"\n  [{passage.passage_id}] section: {passage.section}, page {passage.page}, "
                f"{passage.word_count} words"
            )
            print(f"  {preview(passage.text)}")

    print("\nChunk timings:")
    for name, seconds in timings:
        print(f"  {name}: {seconds * 1000:.1f} ms")
    print(f"\n{'PASS' if all_passed else 'FAIL'}: checkpoint 2 automated checks")
    print("Review the samples above: each should read sensibly on its own (SC-003: 9 of 10).")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
