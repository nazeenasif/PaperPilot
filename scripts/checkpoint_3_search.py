"""Checkpoint 3: add papers and search them by meaning (SC-004, SC-006, SC-007, SC-010, SC-011).

With a folder, adds every PDF, searches, checks duplicates and saves the results. Without
one, adds nothing and checks that the saved search gives the same results (persistence).

Usage: python scripts/checkpoint_3_search.py [papers_dir]
"""

import json
import sys
import time
from pathlib import Path

# Allow `python scripts/checkpoint_3_search.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from paperpilot import store  # noqa: E402
from paperpilot.config import load_settings  # noqa: E402
from paperpilot.errors import PaperPilotError  # noqa: E402
from paperpilot.library import add_paper, search  # noqa: E402

QUERY = "what dataset was used for evaluation?"
MAX_ADD_SECONDS = 60.0  # SC-010, warm model
MAX_SEARCH_SECONDS = 2.0  # SC-011, warm model
SCORE_BAND = (0.45, 0.8)  # SC-004 sanity band, not a pass/fail threshold
PREVIEW_CHARS = 200
SAVED_RESULTS = Path(__file__).resolve().parents[1] / "data" / "checkpoint3_last.json"


def check_persistence() -> int:
    """Rerun the saved search on the existing library; PASS if the same passages come back in order."""
    print("Checkpoint 3: persistence (nothing is added)")
    if not SAVED_RESULTS.is_file():
        print(f"FAIL: {SAVED_RESULTS} not found; run with a papers folder first")
        return 1
    saved = json.loads(SAVED_RESULTS.read_text(encoding="utf-8"))
    papers = {m["paper_id"] for m in store.all_metadata()}
    print(f"Library: {load_settings().library_dir}   papers stored: {len(papers)}")
    print(f"Model load: {store.load_model():.1f} s")

    results = search(saved["query"])
    ids = [r.passage_id for r in results]
    query = saved["query"]
    print(f'\nSearch: "{query}"')
    print("  rank  saved passage        now passage          saved score  now score")
    for rank in range(max(len(ids), len(saved["passage_ids"]))):
        saved_id = saved["passage_ids"][rank] if rank < len(saved["passage_ids"]) else "-"
        saved_score = f"{saved['scores'][rank]:.3f}" if rank < len(saved["scores"]) else "-"
        now_id = ids[rank] if rank < len(ids) else "-"
        now_score = f"{results[rank].score:.3f}" if rank < len(results) else "-"
        print(f"  #{rank + 1:<4} {saved_id:<20} {now_id:<20} {saved_score:<12} {now_score}")

    passed = ids == saved["passage_ids"]
    print(f"\n{'PASS' if passed else 'FAIL'}: same passages in the same order after restart (SC-006)")
    return 0 if passed else 1


def main() -> int:
    """Add every PDF, run the evaluation query, print results and PASS/FAIL lines; 0 if all pass."""
    if len(sys.argv) == 1:
        return check_persistence()
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    papers = sorted(Path(sys.argv[1]).glob("*.pdf"))
    if not papers:
        print(f"FAIL: no PDFs found in {sys.argv[1]}")
        return 1

    settings = load_settings()
    print("Checkpoint 3: add and search")
    print(f"Library: {settings.library_dir}   TOP_K={settings.top_k}")
    print(f"Model load: {store.load_model():.1f} s (excluded from timing checks)")

    all_passed, add_seconds = True, []
    print("\nAdding papers:")
    for path in papers:
        start = time.perf_counter()
        try:
            result = add_paper(path)
        except PaperPilotError as error:
            print(f"  FAIL {path.name}: {error}")
            all_passed = False
            continue
        seconds = time.perf_counter() - start
        add_seconds.append(seconds)
        t = result.timings
        print(
            f"  {path.name}: {result.title} | {result.passage_count} passages | "
            f"parse {t['parse']:.2f} s, embed {t['embed']:.2f} s, store {t['store']:.2f} s, total {seconds:.2f} s"
        )

    print(f'\nSearch: "{QUERY}"')
    start = time.perf_counter()
    results = search(QUERY)
    search_seconds = time.perf_counter() - start
    SAVED_RESULTS.parent.mkdir(parents=True, exist_ok=True)
    SAVED_RESULTS.write_text(
        json.dumps({"query": QUERY, "passage_ids": [r.passage_id for r in results], "scores": [r.score for r in results]}),
        encoding="utf-8",
    )
    for r in results:
        print(f"\n  #{r.rank}  score {r.score:.3f}  {r.title}")
        print(f"      section: {r.section}, page {r.page}")
        print(f"      {r.text[:PREVIEW_CHARS]}...")

    print("\nRe-adding papers (duplicate check):")
    count_before = store.get_collection().count()
    all_already_present = True
    for path in papers:
        try:
            again = add_paper(path)
        except PaperPilotError as error:
            print(f"  FAIL {path.name}: {error}")
            all_already_present = False
            continue
        print(f"  {path.name}: already_present={again.already_present}, {again.passage_count} passages")
        all_already_present = all_already_present and again.already_present
    count_after = store.get_collection().count()

    scores = [r.score for r in results]
    print()
    checks = [
        (all_already_present, "every re-added paper is reported as already present (SC-007)"),
        (count_after == count_before, f"total passages unchanged by re-adding ({count_before} -> {count_after})"),
        (0 < len(results) <= settings.top_k, f"1 to {settings.top_k} results (got {len(results)})"),
        (scores == sorted(scores, reverse=True), "scores in descending order"),
        (all(0.0 <= s <= 1.0 for s in scores), "all scores between 0 and 1"),
        (
            bool(add_seconds) and max(add_seconds) < MAX_ADD_SECONDS,
            f"every add under {MAX_ADD_SECONDS:.0f} s (slowest {max(add_seconds, default=0):.2f} s)",
        ),
        (search_seconds < MAX_SEARCH_SECONDS, f"search under {MAX_SEARCH_SECONDS:.0f} s ({search_seconds:.3f} s)"),
    ]
    for passed, description in checks:
        print(f"{'PASS' if passed else 'FAIL'}: {description}")
        all_passed = all_passed and passed

    low, high = SCORE_BAND
    top = scores[0] if scores else 0.0
    in_band = "inside" if low <= top <= high else "outside"
    print(f"INFO: top score {top:.3f} is {in_band} the {low}-{high} sanity band (ranking matters more)")
    print(f"\n{'PASS' if all_passed else 'FAIL'}: checkpoint 3 automated checks")
    print("Review the results above: they should be about evaluation data (SC-004).")
    print(f"Saved results to {SAVED_RESULTS}; run again with no argument to check persistence.")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
