"""The results table: `eval/results.md` and the README block, generated from `eval/results/`,
`eval/experiments.json` and `eval/golden.json` only (spec FR-028, FR-029, SC-008; research R11).
No cache, no PDFs and no model, so it runs on a fresh clone and gives the same output twice.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from evaluation import experiments, golden
from evaluation.retrieval import RESULTS_DIR

RESULTS_MD = Path("eval") / "results.md"
README = Path("README.md")
START = "<!-- eval-results:start -->"
END = "<!-- eval-results:end -->"
NOT_MEASURED = "not measured"
HEADER = ("| Experiment | Change | hit@1 | hit@6 | hit@10 | MRR | Near-misses gated | Retrieval s/question "
          "| Faithfulness | Correct refusals | Requests | Takeaway |")
RULE = "|---|---|---|---|---|---|---|---|---|---|---|---|"


@dataclass(frozen=True)
class Report:
    """The generated texts: the table alone, the whole results.md and the README block."""

    table: str
    markdown: str
    readme_block: str


def _figure(value) -> str:
    return "—" if value is None else f"{value:.3f}"


def _cell(text: str) -> str:
    return str(text).replace("|", "/").replace("\n", " ")


def describe(changes: dict) -> str:
    """The one setting an experiment changes, in words."""
    if not changes:
        return "—"
    if "retrieval" in changes:
        r = changes["retrieval"]
        if r.get("method") == "rerank":
            return f"rerank the vector top {r.get('shortlist', 20)} with {r.get('reranker', '?').split('/')[-1]}"
        if r.get("method") == "hybrid":
            return f"BM25 + vector top {r.get('shortlist', 20)}, fused by RRF (k = {r.get('rrf_k', 60)})"
        return f"retrieval: {json.dumps(r, sort_keys=True)}"
    if changes.get("embed_prefix"):
        return "embed title and section before the passage text"
    if "answer_model" in changes:
        return f"answer with {changes['answer_model']}"
    if "reasoning_effort" in changes:
        return f"reasoning effort {changes['reasoning_effort']}"
    if "scope_rule" in changes:
        return f"scope rule {'on' if changes['scope_rule'] else 'off'}"
    return json.dumps(changes, sort_keys=True)


def _load_results(results_dir: Path) -> dict[str, dict]:
    return {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in sorted(results_dir.glob("*.json"))}


def _row(experiment: experiments.Experiment, result: dict | None, golden_sha: str) -> str | None:
    change = describe(experiment.changes)
    if experiment.base:
        change = f"{experiment.base} + {change}"
    change = _cell(change)
    if result is None:
        if experiment.optional:
            return None
        return f"| {experiment.name} | {change} | not run | | | | | | | | | |"
    name = experiment.name
    if result["configuration"]["golden"]["sha256"] != golden_sha:
        name += " (earlier golden set)"
    if result.get("self_graded"):
        name += " (self-graded)"
    r = result["retrieval"]
    gated = r["gated_not_found"]
    answers = result.get("answers")
    faithfulness = _figure(answers.get("faithfulness")) if answers else NOT_MEASURED
    refusals = _figure(answers.get("correct_refusals")) if answers else NOT_MEASURED
    requests = result.get("requests", {}).get("planned", 0)
    takeaway = _cell(experiment.takeaway) if experiment.takeaway else "no takeaway yet"
    return (f"| {name} | {change} | {_figure(r['hit@1'])} | {_figure(r['hit@6'])} | {_figure(r['hit@10'])} "
            f"| {_figure(r['mrr'])} | {gated['gated']} of {gated['of']} | {r['latency_s']} | {faithfulness} "
            f"| {refusals} | {requests} | {takeaway} |")


def _golden_lines(loaded: golden.GoldenSet, note: str | None) -> list[str]:
    kinds = {}
    for q in loaded.questions:
        kinds[q.get("kind")] = kinds.get(q.get("kind"), 0) + 1
    answerable = sum(n for kind, n in kinds.items() if kind in golden.ANSWERABLE)
    parts = ", ".join(f"{n} {kind.replace('_', '-')}" for kind, n in kinds.items())
    lines = [f"**Golden set**: {len(loaded.questions)} questions ({parts}) over {len(loaded.papers)} papers, "
             f"version {loaded.version}."]
    if note:
        lines[0] += f" {note}"
    step = round(100 / answerable) if answerable else 0
    lines += [
        "",
        "**Limits**:",
        f"- The set is small: {answerable} answerable questions, so one question moves hit@k by {step} points. "
        "Treat differences of one or two questions as noise.",
        "- Retrieval only: answer quality, faithfulness and the LLM judge are future work, so those columns read "
        "\"not measured\".",
        "- Every row gates on the top vector score; near-misses gated means the question would be refused "
        "without a model request.",
        "- Each row is one deterministic run on this CPU; latency excludes model loading.",
    ]
    return lines


def build_report(results_dir: Path | str = RESULTS_DIR, experiments_file: Path | str = experiments.EXPERIMENTS_FILE,
                 golden_file: Path | str = golden.GOLDEN_FILE) -> Report:
    """Build the table, results.md and the README block from the stored files."""
    loaded = golden.load_golden(golden_file)
    results = _load_results(Path(results_dir))
    listed = experiments.load_experiments(experiments_file)
    conclusion = json.loads(Path(experiments_file).read_text(encoding="utf-8")).get("conclusion")
    lead = [f"**Conclusion**: {conclusion}", ""] if conclusion else []
    rows = [row for e in listed if (row := _row(e, results.get(e.name), loaded.sha256)) is not None]
    table = "\n".join([HEADER, RULE, *rows])
    golden_lines = _golden_lines(loaded, loaded.note)
    measured = [e for e in listed if e.name in results]

    per_kind = ["## Per kind", "", "| Experiment | Kind | Questions | hit@6 | MRR | Gated |", "|---|---|---|---|---|---|"]
    for e in measured:
        for kind, figures in results[e.name]["retrieval"]["per_kind"].items():
            if "mrr" in figures:
                per_kind.append(f"| {e.name} | {kind} | {figures['answerable']} | {_figure(figures['hit@6'])} "
                                f"| {_figure(figures['mrr'])} | |")
            else:
                per_kind.append(f"| {e.name} | {kind} | {figures['questions']} | | | {figures['gated']} |")

    ranks = ["## Evidence rank per question", "",
             "Position of the first passage holding the evidence, within the shortlist of 20 (— not found).", "",
             "| Question | " + " | ".join(e.name for e in measured) + " |",
             "|---|" + "---|" * len(measured)]
    for q in loaded.questions:
        if q.get("kind") not in golden.ANSWERABLE:
            continue
        cells = []
        for e in measured:
            found = {row["id"]: row for row in results[e.name]["questions"]}.get(q["id"])
            cells.append(str(found["rank"]) if found and found["rank"] else "—")
        ranks.append(f"| {q['id']} | " + " | ".join(cells) + " |")

    markdown = "\n".join([
        "# Evaluation results", "",
        "Generated by `python -m evaluation report` from `eval/results/`, `eval/experiments.json` and "
        "`eval/golden.json`. Do not edit by hand.", "",
        *lead, table, "", *golden_lines, "", *per_kind, "", *ranks, "",
        "## Judge calibration", "", "not measured (future work).", "",
    ])
    readme_block = "\n".join([
        "Retrieval quality on PaperPilot's golden set, generated by `python -m evaluation report` "
        "(details in [eval/results.md](eval/results.md)). 0 model requests.", "",
        *lead, table, "", *golden_lines, "",
    ])
    return Report(table=table, markdown=markdown, readme_block=readme_block)


def update_readme(readme: Path | str, block: str) -> None:
    """Replace the text between the markers with `block`, or append a section with the markers."""
    readme = Path(readme)
    raw = readme.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    section = f"{START}\n{block}{END}"
    if START in text and END in text:
        before, rest = text.split(START, 1)
        after = rest.split(END, 1)[1]
        text = before + section + after
    else:
        text = text.rstrip("\n") + "\n\n## Evaluation results\n\n" + section + "\n"
    readme.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))


def write_report(results_dir=RESULTS_DIR, experiments_file=experiments.EXPERIMENTS_FILE,
                 golden_file=golden.GOLDEN_FILE, readme=README, out=RESULTS_MD) -> Report:
    """Write results.md and the README block."""
    built = build_report(results_dir, experiments_file, golden_file)
    Path(out).write_text(built.markdown, encoding="utf-8")
    update_readme(readme, built.readme_block)
    return built
