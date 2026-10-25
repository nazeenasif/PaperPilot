"""Checkpoint 7: summaries and comparisons, end to end (Feature 4; guide Checkpoints 6-7).

Talks to the running API (http://127.0.0.1:8000) for the real parts; part `states` runs the engine
in-process with a scripted model and needs no server. Each part states its planned model
requests; the run fails on unplanned requests or when all requests, retries included, exceed
twice the plan (scripts/request_budget.py). Real parts do not start when today's remaining
requests are fewer than their plan.

Usage: python scripts/checkpoint_7_summaries.py [part ...]   (default: every part)
Parts: states (0)

Every claim of the summary is printed with its cited passages (paper, section, page, excerpt)
and written to docs/verification/checkpoint-7-<date>.md for the hand check (FR-027, SC-002).
"""

import os
import sys
import tempfile
import time
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from unittest import mock

# Allow `python scripts/checkpoint_7_summaries.py` from the repo root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import httpx  # noqa: E402

from checkpoint_6_web import API, WRITE_HEADERS, Run, parse_events, wait_until_ready  # noqa: E402
from paperpilot import prompts  # noqa: E402
from paperpilot.llm import MAX_OUTPUT_TOKENS, RequestCounts  # noqa: E402
from request_budget import budget_checks  # noqa: E402

SUMMARY_TIMEOUT = 900.0  # six free-model calls with retries can take minutes
REOPEN_LIMIT = 1.0  # SC-003
EXCERPT = 200
VERIFICATION_DIR = ROOT / "docs" / "verification"


@dataclass
class Claims:
    """Claims collected for the hand check: (source, part, sentence, [passage dict, ...])."""

    rows: list[tuple[str, str, str, list[dict]]] = field(default_factory=list)


@dataclass(frozen=True)
class Part:
    """One checkpoint part: its planned model requests, whether it needs the API, and its runner."""

    plan: int
    needs_api: bool
    run: object


# --- part states (0 requests, in-process) ---

STATES_KEY = "sk-checkpoint-7-states-not-a-real-key"
STATES_ENV = {
    "LLM_PROVIDER": "openrouter", "LLM_BASE_URL": "", "LLM_API_KEY": STATES_KEY,
    "LLM_MODEL": "checkpoint/scripted:free", "LLM_REASONING_EFFORT": "", "RELEVANCE_THRESHOLD": "0.0",
    "DAILY_REQUEST_LIMIT": "50", "CHUNK_WORDS": "220", "CHUNK_OVERLAP": "40", "MIN_CHUNK_WORDS": "30", "TOP_K": "6",
}


def _blocked(*args, **kwargs):
    raise AssertionError("part states tried to reach the model or the provider")


def part_states(run: Run, client: httpx.Client | None, claims: Claims) -> None:
    """Per-part states with a scripted model: a held-back section, a not-reported section, a
    cut-off section and a rejected TL;DR, each with the rest of the summary intact (US4).
    The malformed comparison row is added with comparisons (T033)."""
    sys.path.insert(0, str(ROOT / "tests"))
    import re

    import openai

    from conftest import SUMMARY_SECTIONS, SUMMARY_TITLE, fake_vector, write_pdf
    from paperpilot import llm, service, store
    from paperpilot.errors import LLMError
    from paperpilot.llm import LLMReply

    def scripted(system: str, prompt: str, on_retry=None) -> LLMReply:
        if system == prompts.TLDR_INSTRUCTION:
            return LLMReply("A summary sentence without any citation.", 50, 20, None, 1, 0.0)
        facet = re.search(r"Section: (\w+)\.", prompt).group(1).lower()
        first = re.search(r'<passage id="(\d+)"', prompt).group(1)
        if facet == "method":
            return LLMReply("The method is described without a citation.", 50, 20, None, 1, 0.0)
        if facet == "data":
            return LLMReply("The data comes from passage ninety-nine [99].", 50, 20, None, 1, 0.0)
        if facet == "results":
            raise LLMError("cut off", reason="cut_off")
        return LLMReply(f"The {facet} is stated in the paper [{first}].", 50, 20, None, 1, 0.0)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder, ExitStack() as stack:
        stack.enter_context(mock.patch.dict(os.environ, {**STATES_ENV, "LIBRARY_DIR": str(Path(folder) / "library")}))
        for target, name, value in [
            (openai, "OpenAI", _blocked), (llm, "_make_client", _blocked), (llm, "_fetch_key_info", _blocked),
            (llm, "generate", scripted), (store, "load_model", lambda: 0.0), (store, "embed_query", fake_vector),
            (store, "embed_passages", lambda texts, on_progress=None: [fake_vector(t) for t in texts]),
        ]:
            stack.enter_context(mock.patch.object(target, name, value))
        store.reset_cache()
        stack.callback(store.reset_cache)
        from paperpilot.library import add_paper

        before = llm.request_counts()
        paper = add_paper(write_pdf(Path(folder) / "paper.pdf", sections=SUMMARY_SECTIONS, references=False,
                                    title=SUMMARY_TITLE))
        summary = service.summarize(paper.paper_id)
        parts = {p.part: p for p in [*summary.sections, summary.tldr]}
        for p in parts.values():
            print(f"  {p.part:12} {p.state:13} {p.reason or ''}")
        run.check(parts["data"].state == "held_back" and parts["data"].citations.invalid == [99]
                  and parts["data"].text is None and parts["data"].rejected_text is not None,
                  "held back: a section citing passage 99 shows no text, keeps the unverified text")
        run.check((parts["method"].state, parts["method"].reason) == ("not_reported", "no_citations"),
                  "not reported: a section without citations reads 'Not reported in the retrieved passages'")
        run.check((parts["results"].state, parts["results"].reason, parts["results"].text) == ("failed", "cut_off", None),
                  "cut off: a cut-off section fails alone, with no truncated text")
        run.check(parts["tldr"].state == "held_back" and parts["tldr"].warning == "sentence 1 has no citation",
                  "rejected TL;DR: held back with the broken rule named")
        run.check(all(parts[f].state == "verified" for f in ("problem", "limitations")),
                  "the other sections stay verified and visible")
        used = llm.request_counts() - before
        run.check(used.total == 0, f"states: {used.total} model requests")


PARTS: dict[str, Part] = {
    "states": Part(plan=0, needs_api=False, run=part_states),
}


def write_claims(claims: Claims) -> Path | None:
    """The hand-check record: every claim with its cited passages, Verdict and Fault left empty."""
    if not claims.rows:
        return None
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    path = VERIFICATION_DIR / f"checkpoint-7-{date.today().isoformat()}.md"

    def cell(text: str) -> str:
        return text.replace("|", "\\|").replace("\n", " ")

    lines = [
        f"# Checkpoint 7 claims ({date.today().isoformat()})",
        "",
        "Hand check (FR-027, SC-002): verify at least five claims from each source against the PDFs.",
        "**Verdict**: correct / wrong / partly. **Fault** (for wrong or partly): retrieval (the right",
        "passage was not retrieved) or model (the cited passage does not say it).",
        "",
        "| # | Source | Part | Claim | Cited passages | Verdict | Fault |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, (source, part, sentence, cited) in enumerate(claims.rows, start=1):
        refs = "<br>".join(f"[{p['number']}] {cell(p['title'][:40])}, {cell(p['section'])}, p. {p['page']}: "
                           f"“{cell(p['text'][:EXCERPT])}…”" for p in cited)
        lines.append(f"| {i} | {source} | {part} | {cell(sentence)} | {refs} |  |  |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def print_claims(claims: Claims) -> None:
    print("\nClaims for the hand check:")
    for i, (source, part, sentence, cited) in enumerate(claims.rows, start=1):
        print(f"\n  {i}. [{source} · {part}] {sentence}")
        for p in cited:
            excerpt = " ".join(p["text"].split())[:EXCERPT]
            print(f"     [{p['number']}] {p['title'][:50]} — {p['section']}, p. {p['page']}: \"{excerpt}…\"")


def main() -> int:
    """Run the selected parts; return 0 if every check passes."""
    names = [a.lower() for a in sys.argv[1:]] or list(PARTS)
    unknown = [n for n in names if n not in PARTS]
    if unknown:
        print(f"Unknown part(s) {unknown}; choose from {', '.join(PARTS)} (default: all)")
        return 2

    plan = sum(PARTS[n].plan for n in names)
    print("Checkpoint 7: summaries and comparisons")
    print("Plan:")
    for n in names:
        print(f"  {n:13} {PARTS[n].plan} model requests")
    print(f"  {'total':13} {plan} (cap {2 * plan} with retries)")

    run = Run(results=[], used=RequestCounts(0, 0))
    claims = Claims()
    needs_api = any(PARTS[n].needs_api for n in names)
    with httpx.Client(base_url=API, timeout=30.0) as client:
        if needs_api:
            status = wait_until_ready(client)
            if status is None or status.get("state") != "ready":
                run.check(False, f"the API is ready at {API} (start it with: python -m api)")
                return 1
            run.check(True, f"the API is ready (model {status['model']})")
            left = int(client.get("/api/usage").json()["remaining"])
            print(f"INFO: {left} model requests left today")
            if left < plan:
                run.check(False, f"at least {plan} requests are left today ({left}); nothing was sent")
                return 1
        for name in names:
            print(f"\n=== Part: {name} (planned model requests: {PARTS[name].plan})")
            PARTS[name].run(run, client if PARTS[name].needs_api else None, claims)

    if claims.rows:
        print_claims(claims)
        path = write_claims(claims)
        print(f"\nINFO: {len(claims.rows)} claims written to {path.relative_to(ROOT)} for the hand check")

    used = run.used
    print(f"\nLLM requests: {used.total} ({used.planned} planned, {used.retries} retries; plan {plan}, cap {2 * plan})")
    for passed, description in budget_checks("checkpoint 7", used, plan):
        run.check(passed, description)
    all_passed = all(passed for passed, _ in run.results)
    print(f"\n{'PASS' if all_passed else 'FAIL'}: checkpoint 7 automated checks")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
