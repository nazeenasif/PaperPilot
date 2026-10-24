"""Today's model request usage (spec FR-024–FR-026, ADR-0007). Sends no model requests.

Reads the provider's own count (OpenRouter's key endpoint) when it can, otherwise PaperPilot's
shared local count in <LIBRARY_DIR>/usage.sqlite3. Never prints the key.

Usage: python scripts/usage.py
"""

import sys
from pathlib import Path

# Allow `python scripts/usage.py` from the repo root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from paperpilot import llm  # noqa: E402
from paperpilot.errors import PaperPilotError  # noqa: E402


def main() -> int:
    try:
        usage = llm.refresh_usage()
    except PaperPilotError as error:
        print(f"Could not read usage: {error}", file=sys.stderr)
        return 1
    print(f"Used today:  {usage.used} / {usage.limit}")
    print(f"Remaining:   {usage.remaining}")
    print(f"Resets at:   {usage.resets_at:%Y-%m-%d %H:%M} UTC "
          f"({usage.resets_at.astimezone():%Y-%m-%d %H:%M %Z} local)")
    print(f"Source:      {'the provider' if usage.source == 'provider' else 'PaperPilot local count'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
