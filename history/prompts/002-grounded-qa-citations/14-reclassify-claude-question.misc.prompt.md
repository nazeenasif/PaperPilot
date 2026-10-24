---
id: 14
title: Reclassify Claude Question
stage: misc
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: none (direct request)
labels: ["calibration", "near-miss", "probe", "checkpoint-4"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - scripts/calibrate_threshold.py
 - scripts/checkpoint_4_answer.py
 - eval/probe_notes.md
 - eval/threshold_calibration.md
tests:
 - scripts/calibrate_threshold.py: PASS, 0 LLM requests, suggestion 0.59 unchanged
 - scripts/checkpoint_4_answer.py nearmiss: PASS, 3 LLM requests
---

## Prompt

Move "What is the context window of Claude?" to the on-topic group in the calibration script and add it to eval/probe_notes.md as an answerable question (evidence: "Claude-1.3 (100K) has an extended context length of 100K tokens", Lost in the Middle p. 5). Replace it in the topic-level near-miss group, in both the calibration script and checkpoint 4, with "What is the context window of Claude 3?". Rerun the calibration (0 requests) and confirm the threshold is unchanged. Rerun checkpoint 4 nearmiss (3 requests). Commit.

## Response snapshot

Moved the Claude question to on-topic (0.639) and added it as probe Q6 (answer rank 1, not part
of the 5-query baseline); replaced it with "What is the context window of Claude 3?" (0.662) in
the calibration near-miss group and checkpoint 4. Calibration: on-topic 8 (0.629–0.844),
suggestion still 0.59 = configured; margins unchanged (0.039 / +0.002 / +0.046). Near-miss
rerun: all three not-found (model_not_found), 3 requests, no retries; generate 37.54 s,
14.01 s, 21.10 s — not-found replies can exceed SC-008's 15 s.

## Outcome

- ✅ Impact: question groups now match what the papers actually say; threshold confirmed.
- 🧪 Tests: calibration PASS (0 requests); checkpoint 4 nearmiss PASS (3 requests).
- 📁 Files: see list.
- 🔁 Next prompts: decide how SC-008 treats slow not-found replies; US3.
- 🧠 Reflection: latency of the free model varies widely (4–38 s) for similar prompts.

## Evaluation notes (flywheel)

- Failure modes observed: free-model latency spikes on not-found replies.
- Graders run and results (PASS/FAIL): calibration PASS; checkpoint 4 nearmiss PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): try LLM_REASONING_EFFORT=low on the near-miss part and compare latency and verdicts (3 requests).
