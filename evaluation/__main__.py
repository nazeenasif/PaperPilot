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
    parser = argparse.ArgumentParser(prog="python -m evaluation", description="PaperPilot's evaluation harness")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in COMMANDS.items():
        command = commands.add_parser(name, help=help_text)
        command.add_argument("rest", nargs="*", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one command; return its exit code."""
    args = build_parser().parse_args(argv)
    print(f"{args.command}: not implemented yet")
    return 2


if __name__ == "__main__":
    sys.exit(main())
