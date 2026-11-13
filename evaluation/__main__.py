"""Command line of the evaluation harness: `python -m evaluation <command>` (contracts/cli.md).

Exit codes: 0 every check passed, 1 a failed check or a refused run, 2 bad arguments.
"""

import argparse
import sys
from pathlib import Path

COMMANDS = {
    "check": "validate eval/golden.json and eval/experiments.json (0 requests)",
    "retrieval": "run retrieval experiments (0 requests)",
    "best": "show the best retrieval configuration (0 requests)",
    "answers": "answer the golden questions for an experiment",
    "judge": "judge the stored answers of an experiment",
    "calibrate": "import hand verdicts or calibrate the judge",
    "scope": "the optional scope-rule rows",
    "report": "write eval/results.md and the README block (0 requests)",
    "status": "show each run's progress (0 requests)",
}


def build_parser() -> argparse.ArgumentParser:
    """The argument parser with one subcommand per entry of COMMANDS."""
    from evaluation.experiments import EXPERIMENTS_FILE
    from evaluation.golden import GOLDEN_FILE
    from evaluation.retrieval import RESULTS_DIR

    parser = argparse.ArgumentParser(prog="python -m evaluation", description="PaperPilot's evaluation harness")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in COMMANDS.items():
        command = commands.add_parser(name, help=help_text)
        if name == "check":
            command.add_argument("--golden", default=str(GOLDEN_FILE), help="the golden-set file")
            command.add_argument("--drafts", action="store_true",
                                 help="list unconfirmed items and missing evidence instead of failing")
            command.add_argument("--cross-min-papers", type=int, default=2, help=argparse.SUPPRESS)
        elif name == "retrieval":
            command.add_argument("names", nargs="*", help="experiments to run (default: every retrieval experiment)")
            command.add_argument("--golden", default=str(GOLDEN_FILE), help="the golden-set file")
            command.add_argument("--experiments", default=str(EXPERIMENTS_FILE), help="the experiments file")
            command.add_argument("--results", default=str(RESULTS_DIR), help="where result files are written")
        elif name == "report":
            command.add_argument("--results", default=str(RESULTS_DIR), help="the result files")
            command.add_argument("--experiments", default=str(EXPERIMENTS_FILE), help="the experiments file")
            command.add_argument("--golden", default=str(GOLDEN_FILE), help="the golden-set file")
            command.add_argument("--readme", default="README.md", help="the README to update")
            command.add_argument("--out", default=str(Path("eval") / "results.md"), help="the results page")
        else:
            command.add_argument("rest", nargs="*", help=argparse.SUPPRESS)
    return parser


def run_check(args: argparse.Namespace) -> int:
    """Validate the golden set and the experiments file; print counts, failures and notes."""
    from evaluation import experiments, golden

    sys.stdout.reconfigure(encoding="utf-8")
    failed = False
    try:
        loaded = golden.load_golden(args.golden)
    except (OSError, ValueError) as error:
        print(f"FAIL: {error}")
        return 1
    report = golden.check(loaded, drafts=args.drafts, cross_min_papers=args.cross_min_papers)
    print(f"Golden set {loaded.path} (version {loaded.version}, {len(loaded.questions)} questions)")
    for kind, target in golden.TARGETS.items():
        print(f"  {kind}: {report.counts[kind]} of {target}" if target else f"  {kind}: {report.counts[kind]} (optional)")
    if report.table_answers:
        print("  table answers per paper: " + ", ".join(f"{p} {n}" for p, n in report.table_answers.items()))
    for note in report.notes:
        print(f"TODO: {note}")
    for error in report.errors:
        print(f"FAIL: {error}")
    failed = not report.ok
    try:
        names = [e.name for e in experiments.load_experiments()]
        print(f"Experiments: {len(names)} ({', '.join(names)})")
    except (OSError, ValueError, KeyError) as error:
        print(f"FAIL: experiments: {error}")
        failed = True
    print("PASS" if not failed else "FAIL", "Model requests: 0")
    return 1 if failed else 0


def _figure(value) -> str:
    return "—" if value is None else f"{value:.3f}"


def run_retrieval(args: argparse.Namespace) -> int:
    """Run retrieval experiments (0 model requests): write each result file and print its figures."""
    from evaluation import experiments, golden, retrieval
    from paperpilot import library

    sys.stdout.reconfigure(encoding="utf-8")
    try:
        loaded = golden.load_golden(args.golden)
        known = {e.name: e for e in experiments.load_experiments(args.experiments)}
    except (OSError, ValueError, KeyError) as error:
        print(f"FAIL: {error}")
        return 1
    names = args.names or [name for name, e in known.items() if retrieval.is_retrieval_experiment(e)]
    for name in names:
        if name not in known:
            print(f"{name}: unknown experiment; known: {', '.join(known)}")
            return 2
        if not retrieval.is_retrieval_experiment(known[name]) or (
                known[name].base and not retrieval.is_retrieval_experiment(known[known[name].base])):
            print(f"{name}: not a retrieval experiment (it changes {', '.join(known[name].changes)})")
            return 2
    try:
        paper_ids = retrieval.golden_papers(loaded)
        before = {pid: library.passage_fingerprint(pid) for pid in paper_ids.values()}
        baseline = retrieval.baseline_configuration(loaded)
        rows = []
        for name in names:
            result = retrieval.run_experiment(known[name], loaded, baseline, base=known.get(known[name].base))
            path = retrieval.write_result(result, args.results)
            rows.append(result)
            r = result["retrieval"]
            print(f"{name}: hit@1 {_figure(r['hit@1'])}  hit@3 {_figure(r['hit@3'])}  hit@6 {_figure(r['hit@6'])}  "
                  f"hit@10 {_figure(r['hit@10'])}  MRR {_figure(r['mrr'])}  gated not-founds "
                  f"{r['gated_not_found']['gated']} of {r['gated_not_found']['of']}  {r['latency_s']} s/question  -> {path}")
            for kind, figures in r["per_kind"].items():
                if "mrr" in figures:
                    print(f"    {kind}: hit@6 {_figure(figures['hit@6'])}  MRR {_figure(figures['mrr'])}  ({figures['answerable']})")
                else:
                    print(f"    {kind}: gated {figures['gated']} of {figures['questions']}")
            print("    ranks: " + ", ".join(f"{q['id']} {q['rank'] if q['rank'] else '-'}"
                                          for q in result["questions"] if q["kind"] in golden.ANSWERABLE))
    except ValueError as error:
        print(f"FAIL: {error}")
        return 1
    after = {pid: library.passage_fingerprint(pid) for pid in paper_ids.values()}
    print(f"Library unchanged: {'yes' if after == before else 'NO'}")
    print("Model requests: 0")
    return 0 if after == before else 1


def run_report(args: argparse.Namespace) -> int:
    """Write the results page and the README block from stored results (0 model requests)."""
    from evaluation import report

    sys.stdout.reconfigure(encoding="utf-8")
    try:
        built = report.write_report(args.results, args.experiments, args.golden, args.readme, args.out)
    except (OSError, ValueError, KeyError) as error:
        print(f"FAIL: {error}")
        return 1
    print(built.table)
    print(f"Wrote {args.out} and the block in {args.readme}. Model requests: 0")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run one command; return its exit code."""
    args = build_parser().parse_args(argv)
    if args.command == "check":
        return run_check(args)
    if args.command == "retrieval":
        return run_retrieval(args)
    if args.command == "report":
        return run_report(args)
    print(f"{args.command}: not implemented yet")
    return 2


if __name__ == "__main__":
    sys.exit(main())
