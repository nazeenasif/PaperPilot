"""Checkpoint 6 (geometry): how many passages get exact highlights (spec SC-002 proxy, ADR-0006).

Parses and chunks each PDF exactly as ingest does and counts passages whose every word was
located (word-level regions), those that fell back to whole block lines, and those without
regions. No embedding, no model requests.

Usage: python scripts/checkpoint_6_geometry.py [pdf ...]   (default: every PDF in papers/)
"""

import sys
from pathlib import Path

# Allow `python scripts/checkpoint_6_geometry.py` from the repo root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Print Unicode (−, ﬁ, Θ) on a Windows console without PYTHONIOENCODING.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from paperpilot.config import load_settings  # noqa: E402
from paperpilot.errors import PaperPilotError  # noqa: E402
from paperpilot.ingest import build_layout, chunk_sections, parse_pdf  # noqa: E402

TARGET = 0.90  # SC-002: at least 90% of citations show the passage highlighted


def main() -> int:
    """Measure word-level highlight coverage; return 0 if it meets the target."""
    paths = [Path(a) for a in sys.argv[1:]] or sorted((ROOT / "papers").glob("*.pdf"))
    if not paths:
        print("FAIL: no PDFs found (put the test papers in papers/ or pass paths)")
        return 1
    settings = load_settings()
    print(f"Checkpoint 6 (geometry): {len(paths)} PDF(s), chunking {settings.chunk_words}/{settings.chunk_overlap}")
    print(f"\n{'Paper':<52} {'Passages':>8} {'Exact':>6} {'Lines':>6} {'None':>5} {'Exact %':>8}")
    totals = [0, 0, 0, 0]
    failed = False
    for path in paths:
        try:
            paper = parse_pdf(path)
        except PaperPilotError as error:
            print(f"FAIL: {path.name}: {type(error).__name__}: {error}")
            failed = True
            continue
        passages = chunk_sections(paper.sections, paper.paper_id, paper.title, settings)
        layout = build_layout(paper, passages, settings)
        exact = sum(1 for p in passages if p.exact_regions)
        lines = sum(1 for p in passages if p.regions and not p.exact_regions)
        none = sum(1 for p in passages if not p.regions)
        assert len(layout["passages"]) == len(passages)
        for i, value in enumerate((len(passages), exact, lines, none)):
            totals[i] += value
        share = exact / len(passages) if passages else 0.0
        print(f"{paper.title[:52]:<52} {len(passages):>8} {exact:>6} {lines:>6} {none:>5} {share:>7.1%}")

    count, exact, lines, none = totals
    share = exact / count if count else 0.0
    print(f"{'All papers':<52} {count:>8} {exact:>6} {lines:>6} {none:>5} {share:>7.1%}")
    print("\nExact: every word located (word-level boxes); Lines: whole block lines used; None: no regions.")
    passed = not failed and count > 0 and share >= TARGET
    print(f"\n{'PASS' if passed else 'FAIL'}: {share:.1%} of passages have exact word-level highlights "
          f"(target {TARGET:.0%}, SC-002)")
    print("LLM requests: 0 (plan 0)")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
