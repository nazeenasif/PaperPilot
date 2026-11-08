"""A cut-off part keeps its token counts (research R5), and the checkpoint report shows the split
for every part. Fake client and scripted model only; no network."""

import sys
from pathlib import Path

import pytest

import fake_llm as f
from paperpilot import llm, service
from paperpilot.errors import LLMError
from test_summarize import PromptReadingLLM

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from checkpoint_7_summaries import Claims, token_rows, token_table  # noqa: E402

COUNTS = {"input": 500, "output": 8192, "reasoning": 8100}


def test_a_cut_off_error_carries_the_token_counts(monkeypatch, llm_env):
    fake = f.FakeClient([f.length(reasoning_tokens=3000)])
    monkeypatch.setattr(llm, "_make_client", lambda settings: fake)
    with pytest.raises(LLMError) as raised:
        llm.generate("system", "prompt", task="summary_section")
    assert raised.value.reason == "cut_off"
    assert raised.value.tokens == {"input": 500, "output": 3000, "reasoning": 3000}


def test_other_failures_carry_no_counts():
    assert LLMError("no answer", reason="empty").tokens is None


class CutOff(PromptReadingLLM):
    """Cuts off one part, with counts when given."""

    def __init__(self, part, tokens=None):
        super().__init__()
        self.part, self.tokens = part, tokens

    def __call__(self, system, prompt, on_retry=None, task="answer"):
        if self.part in prompt:
            raise LLMError("cut off", reason="cut_off", tokens=self.tokens)
        return super().__call__(system, prompt, on_retry, task)


def test_a_cut_off_section_keeps_its_counts_when_saved(summary_env, monkeypatch):
    monkeypatch.setattr(llm, "generate", CutOff("Section: Results.", COUNTS))
    summary = service.summarize(summary_env.paper_id)
    results = next(s for s in summary.sections if s.part == "results")
    assert (results.state, results.reason, results.tokens) == ("failed", "cut_off", COUNTS)
    saved = service.saved_summary(summary_env.paper_id)
    assert next(s for s in saved.sections if s.part == "results").tokens == COUNTS


def test_a_cut_off_tldr_keeps_its_counts(summary_env, monkeypatch):
    monkeypatch.setattr(llm, "generate", CutOff("<section", COUNTS))
    summary = service.summarize(summary_env.paper_id)
    assert (summary.tldr.state, summary.tldr.tokens) == ("failed", COUNTS)


def part(name, state="verified", tokens=None, reason=None):
    return {"part": name, "state": state, "tokens": tokens or {}, "reason": reason}


def test_token_rows_give_the_split_for_every_part_in_order():
    summary = {
        "tldr": part("tldr", tokens={"input": 900, "output": 1474, "reasoning": 1382}),
        "sections": [
            part("problem", tokens={"input": 800, "output": 1141, "reasoning": 1065}),
            part("results", "failed", COUNTS, "cut_off"),
            part("data", "failed", {}, "empty"),
        ],
    }
    assert token_rows(summary) == [
        ("TL;DR", "verified", 900, 1474, 1382, 92),
        ("Problem", "verified", 800, 1141, 1065, 76),
        ("Results", "failed (cut_off)", 500, 8192, 8100, 92),
        ("Data", "failed (empty)", None, None, None, None),
    ]


def test_the_token_table_marks_counts_the_provider_did_not_report():
    lines = token_table([("Results", "failed (cut_off)", 500, 8192, 8100, 92), ("Data", "failed (empty)", None, None, None, None)])
    assert lines[0].startswith("| Part | State | Input | Output | Reasoning | Visible |")
    assert "| Results | failed (cut_off) | 500 | 8,192 | 8,100 | 92 |" in lines
    assert "| Data | failed (empty) | not reported | not reported | not reported | not reported |" in lines


def test_the_report_includes_the_token_split(tmp_path, monkeypatch):
    import checkpoint_7_summaries as checkpoint

    monkeypatch.setattr(checkpoint, "VERIFICATION_DIR", tmp_path)
    claims = Claims(tokens=[("Results", "failed (cut_off)", 500, 8192, 8100, 92)])
    text = checkpoint.write_claims(claims).read_text(encoding="utf-8")
    assert "## Tokens per part" in text and "| Results | failed (cut_off) | 500 | 8,192 | 8,100 | 92 |" in text
