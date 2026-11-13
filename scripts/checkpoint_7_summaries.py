"""Checkpoint 7: summaries and comparisons, end to end (Feature 4; guide Checkpoints 6-7).

Talks to the running API (http://127.0.0.1:8000) for the real parts; part `states` runs the engine
in-process with a scripted model and needs no server. Each part states its planned model
requests; the run fails on unplanned requests or when all requests, retries included, exceed
twice the plan (scripts/request_budget.py). Real parts do not start when today's remaining
requests are fewer than their plan.

Usage: python scripts/checkpoint_7_summaries.py [part ...]   (default: every part but retry)
Parts: states (0), summary (6, LoRA), retry (2: Results and the TL;DR of the saved LoRA summary),
reopen (0, needs summary or a saved LoRA summary), compare (3, BERT vs RAG on Method, Datasets,
Results), not-reported (1, BERT vs RAG on Limitations)

Every claim of the summary is printed with its cited passages (paper, section, page, excerpt)
and written to docs/verification/checkpoint-7-<date>.md for the hand check (FR-027, SC-002); a
later run on the same day adds -v2, -v3 and so on, so a filled-in hand check is never overwritten.
"""

import json
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
from paperpilot.llm import OUTPUT_TOKENS, RequestCounts  # noqa: E402
from request_budget import budget_checks  # noqa: E402

PART_TOKENS = OUTPUT_TOKENS["summary_section"]  # the same for the TL;DR
SUMMARY_TIMEOUT = 900.0  # six free-model calls with retries can take minutes
REOPEN_LIMIT = 1.0  # SC-003
EXCERPT = 200
VERIFICATION_DIR = ROOT / "docs" / "verification"


@dataclass
class Claims:
    """Claims collected for the hand check: (source, part, sentence, [passage dict, ...])."""

    rows: list[tuple[str, str, str, list[dict]]] = field(default_factory=list)
    tokens: list[tuple] = field(default_factory=list)  # token_rows() of the summary


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
    Then a comparison with one malformed row and the other intact."""
    sys.path.insert(0, str(ROOT / "tests"))
    import re

    import openai

    from conftest import SECOND_SECTIONS, SECOND_TITLE, SUMMARY_SECTIONS, SUMMARY_TITLE, fake_vector, write_pdf
    from paperpilot import llm, service, store
    from paperpilot.errors import LLMError
    from paperpilot.llm import LLMReply

    def scripted(system: str, prompt: str, on_retry=None, task: str = "answer") -> LLMReply:
        if system == prompts.ROW_INSTRUCTION:
            if "Row: Method." in prompt:
                return LLMReply("This is not the JSON that was asked for.", 50, 20, None, 1, 0.0)
            cells = [{"paper": label, "text": f"The results are stated here [{number}]."}
                     for label, number in re.findall(r'Paper (P\d):[^<]*<passage id="(\d+)"', prompt)]
            return LLMReply(json.dumps({"cells": cells}), 50, 20, None, 1, 0.0)
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

        second = add_paper(write_pdf(Path(folder) / "second.pdf", sections=SECOND_SECTIONS, references=False,
                                     title=SECOND_TITLE))
        compared = service.compare([paper.paper_id, second.paper_id], ["method", "results"])
        method, results = compared.rows
        print(f"  {'method row':12} {method.state:13} {method.reason or ''}")
        print(f"  {'results row':12} {results.state:13} {compared.verified_cells} of {compared.total_cells} cells verified")
        run.check((method.state, method.reason, method.cells) == ("failed", "malformed", []),
                  "malformed row: fails alone, with no cells")
        run.check(results.state == "ok" and all(c.state == "verified" for c in results.cells),
                  "the other row stays verified and visible")
        used = llm.request_counts() - before
        run.check(used.total == 0, f"states: {used.total} model requests")


# --- part summary (6 requests) and reopen (0) ---


def find_paper(client: httpx.Client, prefix: str) -> dict | None:
    for paper in client.get("/api/papers").json()["papers"]:
        if paper["title"].lower().startswith(prefix.lower()):
            return paper
    return None


def remaining(client: httpx.Client) -> int:
    return int(client.get("/api/usage").json()["remaining"])


def claim_rows(source: str, summary: dict) -> list[tuple[str, str, str, list[dict]]]:
    """Every sentence of every verified part, with the passages it cites."""
    passages = {p["number"]: p for p in summary["passages"]}
    rows = []
    for part in [summary["tldr"], *summary["sections"]]:
        if part["state"] != "verified" or not part["text"]:
            continue
        for sentence in prompts._sentences(part["text"]):  # the validator's own sentence rule
            cited = [passages[n] for n in prompts.extract_citations(sentence) if n in passages]
            rows.append((source, part["part"], sentence, cited))
    return rows


def _label(name: str) -> str:
    return "TL;DR" if name == "tldr" else prompts.FACETS[name].label


def token_rows(summary: dict) -> list[tuple]:
    """(part, state, input, output, reasoning, visible) for every part, failed ones too. Visible is
    output minus reasoning, since the provider's output count includes reasoning."""
    rows = []
    for part in [summary["tldr"], *summary["sections"]]:
        tokens = part["tokens"] or {}
        output, reasoning = tokens.get("output"), tokens.get("reasoning")
        visible = output - reasoning if output is not None and reasoning is not None else None
        state = f"{part['state']} ({part['reason']})" if part["reason"] else part["state"]
        rows.append((_label(part["part"]), state, tokens.get("input"), output, reasoning, visible))
    return rows


def token_table(rows: list[tuple]) -> list[str]:
    """The token split as Markdown table lines."""

    def count(value: int | None) -> str:
        return "not reported" if value is None else f"{value:,}"

    return ["| Part | State | Input | Output | Reasoning | Visible |", "|---|---|---|---|---|---|",
            *(f"| {name} | {state} | " + " | ".join(count(v) for v in values) + " |" for name, state, *values in rows)]


def print_summary(summary: dict) -> None:
    passages = {p["number"]: p for p in summary["passages"]}
    print(f"\nSummary of {summary['title']} ({summary['model']}, {summary['created_at']})")
    for part in [summary["tldr"], *summary["sections"]]:
        label = _label(part["part"])
        tokens = part["tokens"]  # the provider's output count already includes reasoning
        print(f"\n  [{label}] {part['state']}" + (f" ({part['reason']})" if part["reason"] else "")
              + (f" · tokens {tokens.get('output')} of {PART_TOKENS}, {tokens.get('reasoning')} of them reasoning"
                 if tokens else ""))
        if part["text"]:
            print(f"    {part['text']}")
        if part["rejected_text"]:
            print(f"    NOT VERIFIED: {part['rejected_text']}")
            print(f"    warning: {part['warning']}")
        if part["sources"] and any(part["sources"]):
            print(f"    sources per sentence: {part['sources']}")
    print("\n  Passages:")
    for n in sorted(passages):
        p = passages[n]
        print(f"    [{n}] {p['section']}, p. {p['page']} ({p['score']:.3f})")


def part_summary(run: Run, client: httpx.Client, claims: Claims) -> None:
    """US1: regenerate the LoRA summary through the API (plan 6); every citation valid and opening."""
    _summary_run(run, client, claims, {"regenerate": True}, 6)


def part_retry(run: Run, client: httpx.Client, claims: Claims) -> None:
    """FR-020: rerun Results and the TL;DR of the saved LoRA summary (plan 2)."""
    _summary_run(run, client, claims, {"retry_parts": ["results", "tldr"]}, 2)


def _summary_run(run: Run, client: httpx.Client, claims: Claims, body: dict, plan: int) -> None:
    """Post one summary run and check it: within its plan, citations valid and opening."""
    lora = find_paper(client, "LoRA")
    if lora is None:
        run.check(False, "the LoRA paper is in the library")
        return
    start = time.monotonic()
    with client.stream("POST", f"/api/summaries/{lora['paper_id']}", json=body,
                       headers=WRITE_HEADERS, timeout=SUMMARY_TIMEOUT) as response:
        text = "".join(response.iter_text())
    seconds = time.monotonic() - start
    if response.status_code != 200:
        run.check(False, f"POST /api/summaries answered {response.status_code}: {text[:200]}")
        return
    events = parse_events(text)
    for name, data in events:
        if name == "progress" and data["step"] in ("reading", "generating"):
            extra = f" ({data['passages']} passages)" if "passages" in data else ""
            print(f"  progress: {data['part']} {data['step']}{extra}")
        elif name == "retry_wait":
            print(f"  retry_wait: {data['part']} attempt {data['attempt']} of {data['max_attempts']}, "
                  f"{data['wait_seconds']:.0f} s ({data['reason']})")
        elif name == "part":
            print(f"  part: {data['part']} {data['state']}")
    final_name, summary = events[-1] if events else ("", {})
    if final_name != "summary":
        run.check(False, f"the stream ended with {final_name or 'nothing'}: {summary}")
        return
    run.add_requests(summary["requests"])
    print_summary(summary)
    print(f"\n  Requests for this summary: {summary['requests']['planned']} planned, "
          f"{summary['requests']['retries']} retries; {seconds:.1f} s")

    run.check(summary["requests"]["planned"] <= plan,
              f"the summary stayed within its plan ({summary['requests']['planned']} of {plan})")
    shown = [p for p in [summary["tldr"], *summary["sections"]] if p["state"] == "verified"]
    run.check(all(not p["citations"]["invalid"] and set(p["citations"]["valid"]) <= set(p["passages"]) for p in shown),
              f"every shown citation is valid for its part ({len(shown)} of 6 parts verified)")
    cut_off = [p["part"] for p in [summary["tldr"], *summary["sections"]] if p["reason"] == "cut_off"]
    run.check(not cut_off, f"every part fit the output budget of {PART_TOKENS} tokens, reasoning included"
                           + (f" (cut off: {', '.join(cut_off)})" if cut_off else ""))

    passages = {p["number"]: p for p in summary["passages"]}
    cited = sorted({n for p in shown for n in p["citations"]["valid"]})
    opened = 0
    for n in cited:
        view = client.get(f"/api/passages/{passages[n]['passage_id']}")
        pdf = client.get(f"/api/papers/{passages[n]['paper_id']}/pdf")
        if view.status_code == 200 and pdf.status_code == 200 and 1 <= view.json()["page"] <= view.json()["page_count"]:
            opened += 1
    run.check(opened == len(cited), f"every cited passage opens its PDF at the cited page ({opened}/{len(cited)})")
    claims.rows += claim_rows("LoRA summary", summary)
    claims.tokens += token_rows(summary)


# --- parts compare (3 requests) and not-reported (1) ---


def foreign_citations(comparison: dict) -> list[tuple[str, int]]:
    """(cell, number) for every shown citation pointing at another paper's passage (FR-010)."""
    owner = {p["number"]: p["paper_id"] for p in comparison["passages"]}
    return [(cell["part"], number) for row in comparison["rows"] for cell in row["cells"] if cell["state"] == "verified"
            for number in cell["citations"]["valid"] if owner.get(number) != cell["part"].split(":", 1)[1]]


def cell_rows(source: str, comparison: dict) -> list[tuple[str, str, str, list[dict]]]:
    """Every sentence of every verified cell, with the passages it cites."""
    passages = {p["number"]: p for p in comparison["passages"]}
    titles = {p["paper_id"]: p["title"] for p in comparison["papers"]}
    rows = []
    for row in comparison["rows"]:
        for cell in row["cells"]:
            if cell["state"] != "verified" or not cell["text"]:
                continue
            paper = titles[cell["part"].split(":", 1)[1]]
            for sentence in prompts._sentences(cell["text"]):
                cited = [passages[n] for n in prompts.extract_citations(sentence) if n in passages]
                rows.append((source, f"{row['aspect']} · {paper}", sentence, cited))
    return rows


def row_token_rows(comparison: dict) -> list[tuple]:
    """(row, state, input, output, reasoning, visible) for every row, failed ones too."""
    rows = []
    for row in comparison["rows"]:
        tokens = row["tokens"] or {}
        output, reasoning = tokens.get("output"), tokens.get("reasoning")
        visible = output - reasoning if output is not None and reasoning is not None else None
        state = f"{row['state']} ({row['reason']})" if row["reason"] else row["state"]
        rows.append((prompts.ASPECTS[row["aspect"]].label, state, tokens.get("input"), output, reasoning, visible))
    return rows


def _compare_run(run: Run, client: httpx.Client, claims: Claims, aspects: list[str], plan: int) -> dict | None:
    """Regenerate BERT vs RAG on some aspects through the API; every shown citation valid and opening."""
    papers = [find_paper(client, prefix) for prefix in ("BERT", "Retrieval-Augmented")]
    if not all(papers):
        run.check(False, "BERT and RAG are in the library")
        return None
    body = {"paper_ids": [p["paper_id"] for p in papers], "aspects": aspects, "regenerate": True}
    start = time.monotonic()
    with client.stream("POST", "/api/comparisons", json=body, headers=WRITE_HEADERS, timeout=SUMMARY_TIMEOUT) as response:
        text = "".join(response.iter_text())
    seconds = time.monotonic() - start
    if response.status_code != 200:
        run.check(False, f"POST /api/comparisons answered {response.status_code}: {text[:200]}")
        return None
    events = parse_events(text)
    for name, data in events:
        if name == "progress" and data["step"] == "generating":
            print(f"  progress: {data['part']} generating")
        elif name == "row_failed":
            print(f"  row_failed: {data['aspect']} ({data['reason']})")
        elif name == "retry_wait":
            print(f"  retry_wait: {data['part']} attempt {data['attempt']} of {data['max_attempts']}, "
                  f"{data['wait_seconds']:.0f} s ({data['reason']})")
    final_name, comparison = events[-1] if events else ("", {})
    if final_name != "comparison":
        run.check(False, f"the stream ended with {final_name or 'nothing'}: {comparison}")
        return None
    run.add_requests(comparison["requests"])

    labels = {p["paper_id"]: p["title"][:30] for p in comparison["papers"]}
    print(f"\nComparison ({comparison['model']}, {comparison['created_at']}), "
          f"{comparison['verified_cells']} of {comparison['total_cells']} cells verified")
    for row in comparison["rows"]:
        print(f"\n  [{row['aspect']}] {row['state']}" + (f" ({row['reason']})" if row["reason"] else ""))
        for cell in row["cells"]:
            print(f"    {labels[cell['part'].split(':', 1)[1]]}: {cell['state']}" + (f" ({cell['reason']})" if cell["reason"] else ""))
            if cell["text"]:
                print(f"      {cell['text']}")
            if cell["rejected_text"]:
                print(f"      NOT VERIFIED: {cell['rejected_text']}")
    print(f"\n  Requests: {comparison['requests']['planned']} planned, {comparison['requests']['retries']} retries; {seconds:.1f} s")

    malformed = sum(row["reason"] == "malformed" for row in comparison["rows"])
    print(f"  Malformed rows: {malformed}")
    run.check(comparison["requests"]["planned"] <= plan,
              f"the comparison stayed within its plan ({comparison['requests']['planned']} of {plan})")
    foreign = foreign_citations(comparison)
    run.check(not foreign, "every shown citation comes from the cell's own paper"
              + (f" (not: {foreign})" if foreign else ""))
    shown = [cell for row in comparison["rows"] for cell in row["cells"] if cell["state"] == "verified"]
    run.check(all(not c["citations"]["invalid"] and set(c["citations"]["valid"]) <= set(c["passages"]) for c in shown),
              f"every shown citation is valid for its cell ({len(shown)} cells verified)")
    passages = {p["number"]: p for p in comparison["passages"]}
    cited = sorted({n for c in shown for n in c["citations"]["valid"]})
    opened = 0
    for n in cited:
        view = client.get(f"/api/passages/{passages[n]['passage_id']}")
        pdf = client.get(f"/api/papers/{passages[n]['paper_id']}/pdf")
        if view.status_code == 200 and pdf.status_code == 200 and 1 <= view.json()["page"] <= view.json()["page_count"]:
            opened += 1
    run.check(opened == len(cited), f"every cited passage opens its PDF at the cited page ({opened}/{len(cited)})")
    claims.rows += cell_rows("BERT vs RAG", comparison)
    claims.tokens += row_token_rows(comparison)
    return comparison


def part_compare(run: Run, client: httpx.Client, claims: Claims) -> None:
    """US3: BERT vs RAG on Method, Datasets and Results (plan 3)."""
    _compare_run(run, client, claims, ["method", "datasets", "results"], 3)


def part_not_reported(run: Run, client: httpx.Client, claims: Claims) -> None:
    """US4: BERT vs RAG on Limitations (plan 1): a cell the paper does not support (SC-004)."""
    comparison = _compare_run(run, client, claims, ["limitations"], 1)
    if comparison is None:
        return
    cells = [cell for row in comparison["rows"] for cell in row["cells"]]
    if any(cell["state"] == "not_reported" for cell in cells):
        run.check(True, "at least one cell reads Not reported in the retrieved passages")
    else:
        print("INFO: no cell was not reported in this run; part states still demonstrates the state (research R11)")


def part_reopen(run: Run, client: httpx.Client, claims: Claims) -> None:
    """US2: the saved LoRA summary reopens in < 1 s with 0 requests (SC-003)."""
    lora = find_paper(client, "LoRA")
    if lora is None:
        run.check(False, "the LoRA paper is in the library")
        return
    used_before = client.get("/api/usage").json()["used"]
    start = time.monotonic()
    response = client.get(f"/api/summaries/{lora['paper_id']}")
    seconds = time.monotonic() - start
    used_after = client.get("/api/usage").json()["used"]
    if response.status_code != 200:
        run.check(False, f"GET /api/summaries answered {response.status_code}: {response.text[:200]}")
        return
    body = response.json()
    print(f"  reopened: {body['status']}, saved {body['created_at']} with {body['model']}, "
          f"{body['verified_parts']} of 6 parts verified, {seconds * 1000:.0f} ms")
    run.check(body["status"] == "current", "the saved summary is current")
    run.check(seconds < REOPEN_LIMIT, f"it reopens within {REOPEN_LIMIT:.0f} s ({seconds * 1000:.0f} ms)")
    run.check(used_after == used_before, f"today's request count is unchanged ({used_before} → {used_after})")


PARTS: dict[str, Part] = {
    "states": Part(plan=0, needs_api=False, run=part_states),
    "summary": Part(plan=6, needs_api=True, run=part_summary),
    "retry": Part(plan=2, needs_api=True, run=part_retry),
    "reopen": Part(plan=0, needs_api=True, run=part_reopen),
    "compare": Part(plan=3, needs_api=True, run=part_compare),
    "not-reported": Part(plan=1, needs_api=True, run=part_not_reported),
}


def claims_path(folder: Path, day: str) -> Path:
    """The first unused report name for this day: never an existing hand-check record."""
    path = folder / f"checkpoint-7-{day}.md"
    version = 2
    while path.exists():
        path = folder / f"checkpoint-7-{day}-v{version}.md"
        version += 1
    return path


DEFAULT_PARTS = [name for name in PARTS if name != "retry"]  # plan 10; retry is run by name


def write_claims(claims: Claims) -> Path | None:
    """The hand-check record: every claim with its cited passages, Verdict and Fault left empty,
    then the token split for every part."""
    if not claims.rows and not claims.tokens:
        return None
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    path = claims_path(VERIFICATION_DIR, date.today().isoformat())

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
    lines += ["", f"## Tokens per part (limit {PART_TOKENS:,}, reasoning included)", "", *token_table(claims.tokens)]
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
    names = [a.lower() for a in sys.argv[1:]] or DEFAULT_PARTS
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
            left = remaining(client)
            print(f"INFO: {left} model requests left today")
            if left < plan:
                run.check(False, f"at least {plan} requests are left today ({left}); nothing was sent")
                return 1
        for name in names:
            print(f"\n=== Part: {name} (planned model requests: {PARTS[name].plan})")
            PARTS[name].run(run, client if PARTS[name].needs_api else None, claims)

    if claims.rows or claims.tokens:
        print_claims(claims)
        print("\nTokens per part:")
        print("\n".join(token_table(claims.tokens)))
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
