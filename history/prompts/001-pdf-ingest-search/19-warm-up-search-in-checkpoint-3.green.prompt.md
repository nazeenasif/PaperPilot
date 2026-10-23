---
id: 19
title: Warm-up Search in Checkpoint 3
stage: green
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 001-pdf-ingest-search
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: none (direct request)
labels: ["checkpoint-3", "timing", "sc-011", "startup"]
links:
  spec: specs/001-pdf-ingest-search/spec.md
  ticket: null
  adr: history/adr/0001-local-retrieval-stack.md
  pr: null
files:
 - scripts/checkpoint_3_search.py
 - specs/001-pdf-ingest-search/research.md
tests:
 - scripts/checkpoint_3_search.py papers: PASS (cold first search 1.567 s reported separately; warm search 0.041 s)
---

## Prompt

Apply the warm-up: in checkpoint 3, run one untimed search before the timed one, print the cold first-search time separately (like model load), and check SC-011 on the warm time. Add a note to research.md: library open and model load are one-time costs (~1–2 s and ~2–8 s); the UI feature must do both at startup. Rerun checkpoint 3 with papers and show only the timing and PASS/FAIL lines. Commit with the pending prompt history record and stop.

## Response snapshot

Checkpoint 3 now runs one warm-up search, prints "Cold first search: … (excluded from timing
checks)", and checks SC-011 as "warm search under 2 s". Added a "One-time startup costs"
note to research R13 (library open ~1–2 s, model load ~2–8 s; UI must do both at startup).
Rerun: model load 3.2 s, first (already-present) add 2.66 s, cold first search 1.567 s,
warm search 0.041 s; all checks PASS, exit 0. Committed with PHRs 18 and 19.

## Outcome

- ✅ Impact: SC-011 measured on per-search cost; checkpoint 3 passes.
- 🧪 Tests: checkpoint 3 PASS.
- 📁 Files: scripts/checkpoint_3_search.py, specs/001-pdf-ingest-search/research.md
- 🔁 Next prompts: US4 (T038–T040) filtered search.
- 🧠 Reflection: The first add still includes opening the library (2.66 s); harmless but visible.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): checkpoint 3 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
