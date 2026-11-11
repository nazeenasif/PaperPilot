"""Command line of the evaluation harness: `python -m evaluation <command>` (contracts/cli.md).

Exit codes: 0 every check passed, 1 a failed check or a refused run, 2 bad arguments.
"""

import argparse
import sys

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
    from evaluation.golden import GOLDEN_FILE

    parser = argparse.ArgumentParser(prog="python -m evaluation", description="PaperPilot's evaluation harness")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in COMMANDS.items():
        command = commands.add_parser(name, help=help_text)
        if name == "check":
            command.add_argument("--golden", default=str(GOLDEN_FILE), help="the golden-set file")
            command.add_argument("--drafts", action="store_true",
                                 help="list unconfirmed items and missing evidence instead of failing")
            command.add_argument("--cross-min-papers", type=int, default=2, help=argparse.SUPPRESS)
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
        print(f"  {kind}: {report.counts[kind]} of {target}")
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


def main(argv: list[str] | None = None) -> int:
    """Run one command; return its exit code."""
    args = build_parser().parse_args(argv)
    if args.command == "check":
        return run_check(args)
    print(f"{args.command}: not implemented yet")
    return 2


if __name__ == "__main__":
    sys.exit(main())
