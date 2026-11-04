"""Facet retrieval probe (Feature 4): which sections do the summary facet queries retrieve?

For each paper in papers/ and each facet, searches with the current query (the same k as
summarize) and reports the sections the passages come from. Problem and Limitations are marked
against the sections they would be expected to draw on. Local embeddings only; no model requests.

Usage: python scripts/probe_facets.py   (also writes eval/facet_probe.md)
"""

import sys
from collections import Counter
from datetime import date
from pathlib import Path

# Allow `python scripts/probe_facets.py` from the repo root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from paperpilot import ingest, library, prompts, store  # noqa: E402
from paperpilot.service import SUMMARY_PASSAGES  # noqa: E402

OUTPUT = ROOT / "eval" / "facet_probe.md"
SHORT = {"attention": "Attention", "bert": "BERT", "retrieval": "RAG", "lora": "LoRA", "lost": "Lost in the Middle"}
# Lower-case words a section name must contain to count as an obvious source for the facet.
OBVIOUS = {
    "problem": ("abstract", "introduction"),
    "limitations": ("limitation", "conclusion", "discussion"),
}


def is_obvious(facet: str, section: str) -> bool:
    return any(word in section.lower() for word in OBVIOUS[facet])


def mark(facet: str, sections: list[str], inventory: Counter) -> str:
    """MISS: none of the passages come from an obvious section the paper has."""
    if facet not in OBVIOUS:
        return ""
    available = [s for s in inventory if is_obvious(facet, s)]
    hits = sum(is_obvious(facet, s) for s in sections)
    if not available:
        return "no such section"
    return "MISS" if hits == 0 else f"{hits}/{len(sections)}"


def main() -> int:
    ids = {ingest.paper_id_for(path.read_bytes()) for path in sorted((ROOT / "papers").glob("*.pdf"))}
    papers = [p for p in library.list_papers() if p.paper_id in ids]
    lines = [
        f"# Facet retrieval probe ({date.today().isoformat()})",
        "",
        f"`python scripts/probe_facets.py`; 0 model requests. Each facet's current query, k = {SUMMARY_PASSAGES},",
        "within one paper, on the 5 papers in `papers/`. Queries not changed. In **Mark**: `n/4` is how many",
        "passages come from an obvious section (Problem: Abstract, Introduction; Limitations: Limitations,",
        "Conclusion, Discussion), `MISS` means none, and `no such section` means the paper has none under",
        "those names. The other facets are not marked.",
        "",
        "| Paper | Facet | Top score | Sections (passages) | Mark |",
        "|---|---|---|---|---|",
    ]
    inventories: list[str] = ["", "## Sections per paper (passages)", ""]
    for paper in papers:
        name = next((v for k, v in SHORT.items() if paper.title.lower().startswith(k)), paper.title[:30])
        inventory = Counter(m["section"] for m in store.paper_metadata(paper.paper_id))
        inventories.append(f"- **{name}**: " + ", ".join(f"{s} ({n})" for s, n in inventory.items()))
        for key, facet in prompts.FACETS.items():
            results = library.search(facet.query, k=SUMMARY_PASSAGES, paper_ids=[paper.paper_id])
            sections = [r.section for r in results]
            counts = ", ".join(f"{s} ({n})" for s, n in Counter(sections).items())
            top = max(r.score for r in results)
            lines.append(f"| {name} | {facet.label} | {top:.3f} | {counts} | {mark(key, sections, inventory)} |")
    text = "\n".join([*lines, *inventories]) + "\n"
    OUTPUT.write_text(text, encoding="utf-8")
    print(text)
    print(f"Written to {OUTPUT.relative_to(ROOT)}. Model requests: 0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
