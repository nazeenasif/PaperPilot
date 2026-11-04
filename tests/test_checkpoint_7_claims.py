"""The checkpoint 7 report never overwrites an earlier hand-check record. No model and no network."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from checkpoint_7_summaries import claims_path  # noqa: E402


def test_the_first_report_of_a_day_has_the_plain_name(tmp_path):
    assert claims_path(tmp_path, "2026-11-04").name == "checkpoint-7-2026-11-04.md"


def test_later_reports_of_the_same_day_get_the_next_version(tmp_path):
    (tmp_path / "checkpoint-7-2026-11-04.md").write_text("filled in", encoding="utf-8")
    assert claims_path(tmp_path, "2026-11-04").name == "checkpoint-7-2026-11-04-v2.md"
    (tmp_path / "checkpoint-7-2026-11-04-v2.md").write_text("filled in", encoding="utf-8")
    assert claims_path(tmp_path, "2026-11-04").name == "checkpoint-7-2026-11-04-v3.md"
