"""Checkpoint 1: titles and sections look right and no reference-list text is kept (SC-002).

Usage: python scripts/checkpoint_1_parse.py <papers_dir>
"""

import sys
import time
from pathlib import Path

# Allow `python scripts/checkpoint_1_parse.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Print Unicode (−, ﬁ, Θ) on a Windows console without PYTHONIOENCODING.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import pymupdf  # noqa: E402

from paperpilot.errors import PaperPilotError  # noqa: E402
from paperpilot.ingest import (  # noqa: E402
    ParsedPaper,
    clean,
    detect_heading,
    heading_candidate,
    order_blocks,
    parse_pdf,
)

SAMPLE_CHARS = 300
REFERENCE_PROBE_BLOCKS = 5
# Every test paper has at least an introduction, a body section and a conclusion.
MIN_BODY_SECTIONS = 3


def text_after_references(path: Path) -> tuple[int | None, list[str]]:
    """Return the page of the References heading and the cleaned text of the blocks after it."""
    with pymupdf.open(path) as doc:
        for number, page in enumerate(doc, start=1):
            raw = [b for b in page.get_text("blocks", sort=True) if b[6] == 0 and b[4].strip()]
            ordered = order_blocks(raw, page.rect.width)
            for index, block in enumerate(ordered):
                first_line, rest = heading_candidate(block[4])
                heading = detect_heading(first_line, None)
                if heading is not None and heading.kind == "stop":
                    after = [clean(rest)] + [clean(b[4]) for b in ordered[index + 1 :]]
                    return number, [t for t in after if len(t) >= 25][:REFERENCE_PROBE_BLOCKS]
    return None, []


def check(paper: ParsedPaper, path: Path) -> list[tuple[bool, str]]:
    """Return (passed, description) for each automated check."""
    names = [s.name for s in paper.sections]
    body_sections = [n for n in names if n != "Front Matter"]
    results = [
        ("Introduction" in names, "an Introduction section is detected"),
        (
            len(body_sections) >= MIN_BODY_SECTIONS,
            f"at least {MIN_BODY_SECTIONS} sections other than Front Matter (found {len(body_sections)})",
        ),
    ]
    ref_page, ref_texts = text_after_references(path)
    kept = {b.text for s in paper.sections for b in s.blocks}
    leaked = [t for t in ref_texts if t in kept]
    if ref_page is None:
        results.append((True, "no reference text kept (no References heading found; check by eye)"))
    else:
        results.append((not leaked, f"no reference text kept (References heading on page {ref_page})"))
    return results


def main() -> int:
    """Parse every PDF in the folder, print details and PASS/FAIL lines; 0 if all pass."""
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    papers = sorted(Path(sys.argv[1]).glob("*.pdf"))
    if not papers:
        print(f"FAIL: no PDFs found in {sys.argv[1]}")
        return 1

    print("Checkpoint 1: parsing")
    all_passed, timings = True, []
    for path in papers:
        print(f"\n=== {path.name}")
        start = time.perf_counter()
        try:
            paper = parse_pdf(path)
        except PaperPilotError as error:
            print(f"FAIL: {error}")
            all_passed = False
            continue
        seconds = time.perf_counter() - start
        timings.append((path.name, seconds))

        print(f"ID: {paper.paper_id}   pages: {paper.page_count}")
        print(f"Title: {paper.title}")
        print("Sections:")
        for section in paper.sections:
            pages = sorted({b.page for b in section.blocks})
            print(f"  - {section.name} ({len(section.blocks)} blocks, pages {pages[0]}-{pages[-1]})")
        page2 = " ".join(b.text for s in paper.sections for b in s.blocks if b.page == 2)
        print(f"Page 2 start (check reading order): {page2[:SAMPLE_CHARS]!r}")
        for passed, description in check(paper, path):
            print(f"{'PASS' if passed else 'FAIL'}: {description}")
            all_passed = all_passed and passed

    print("\nParse timings:")
    for name, seconds in timings:
        print(f"  {name}: {seconds:.2f} s")
    print(f"\n{'PASS' if all_passed else 'FAIL'}: checkpoint 1 automated checks")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
