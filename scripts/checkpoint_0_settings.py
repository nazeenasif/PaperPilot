"""Checkpoint 0: settings load and print without errors (SC-001)."""

import sys
from pathlib import Path

# Allow `python scripts/checkpoint_0_settings.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Print Unicode (−, ﬁ, Θ) on a Windows console without PYTHONIOENCODING.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from paperpilot.config import load_settings  # noqa: E402
from paperpilot.errors import SettingsError  # noqa: E402


def main() -> int:
    """Load and print settings; return 0 on PASS, 1 on FAIL."""
    print("Checkpoint 0: settings")
    try:
        settings = load_settings()
    except SettingsError as error:
        print(f"FAIL: {error}")
        return 1
    print(settings.describe())
    print("PASS: settings loaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
