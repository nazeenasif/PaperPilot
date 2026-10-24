---
id: 19
title: UTF-8 Scripts And Limitation Notes
stage: misc
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: direct request
labels: ["scripts", "windows", "utf-8", "known-limitations", "faithfulness"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - scripts/calibrate_threshold.py
 - scripts/checkpoint_0_settings.py
 - scripts/checkpoint_1_parse.py
 - scripts/checkpoint_2_chunk.py
 - scripts/checkpoint_3_search.py
 - scripts/checkpoint_4_answer.py
 - scripts/checkpoint_5_conversation.py
 - docs/known-limitations.md
 - eval/probe_notes.md
tests:
 - scripts/checkpoint_0_settings.py: exit 0 without PYTHONIOENCODING
 - scripts/calibrate_threshold.py: exit 0 with output redirected to a file (cp1252), 0 LLM requests
---

## Prompt

1. In every script under scripts/, reconfigure stdout and stderr to UTF-8 at startup so output works on a Windows console without PYTHONIOENCODING. Commit.
2. Add to docs/known-limitations.md: title/author-only "Front Matter" passages can take a retrieval slot without adding content (seen for "What is LoRA?"); whether to drop or merge them is an evaluation-feature question. Add F2 to the faithfulness notes as "overgeneralisation when combining passages". Commit.

## Response snapshot

2f9c3f1: all 7 scripts call sys.stdout/sys.stderr.reconfigure(encoding="utf-8") right after
their sys.path setup; calibration (previously crashed on "−") and checkpoint 0 ran without
PYTHONIOENCODING. Second commit: known-limitations Search section gains the Front Matter
bullet (ranked 5th, 0.578, for "What is LoRA?"; drop vs merge left to the evaluation
feature); F2 in eval/probe_notes.md already existed and was retitled "Overgeneralisation when
combining passages".

## Outcome

- ✅ Impact: scripts print Unicode on Windows; limitation and faithfulness category recorded.
- 🧪 Tests: two no-LLM scripts run cleanly; no LLM requests.
- 📁 Files: see list.
- 🔁 Next prompts: US5 (T029–T031).
- 🧠 Reflection: redirecting to a file is the stricter test, since it uses cp1252 too.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): checkpoint 0 PASS; calibration PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
