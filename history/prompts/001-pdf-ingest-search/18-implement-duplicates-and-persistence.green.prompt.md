---
id: 18
title: Implement Duplicates and Persistence
stage: green
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 001-pdf-ingest-search
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: /sp.implement
labels: ["us2", "us3", "duplicates", "persistence", "checkpoint-3", "eval-baseline"]
links:
  spec: specs/001-pdf-ingest-search/spec.md
  ticket: null
  adr: history/adr/0001-local-retrieval-stack.md
  pr: null
files:
 - eval/probe_notes.md
 - specs/001-pdf-ingest-search/spec.md
 - tests/test_library.py
 - paperpilot/library.py
 - paperpilot/store.py
 - scripts/checkpoint_3_search.py
 - specs/001-pdf-ingest-search/contracts/library-api.md
 - specs/001-pdf-ingest-search/tasks.md
tests:
 - pytest (full suite): 175 passed
 - scripts/checkpoint_3_search.py papers: FAIL (duplicate checks PASS; search 2.485 s > 2 s, cold index)
 - scripts/checkpoint_3_search.py (no argument): PASS (same 6 passages, same order, same scores)
---

## Prompt

Update eval/probe_notes.md with a "Baseline" section: library-wide search, k=6, bge-small, 220/40 chunking: hit@6 = 3/5 (one partial), MRR@6 ≈ 0.30 on 5 queries — too few for conclusions. List the three candidate experiments in this order for the evaluation feature: (1) cross-encoder reranking of top 20, (2) hybrid BM25 + vector, (3) title and section prepended to passage text before embedding. Note in the spec that SC-004 is partially met and retrieval quality is owned by the evaluation feature. Commit with the pending prompt history records.

Then /sp.implement T032–T037 (US2 duplicates and US3 persistence). Tests first, commit after each task. Run checkpoint 3 with papers (duplicate section should PASS), then again with no argument (persistence should PASS). Show both outputs and stop.

## Response snapshot

d6af201: probe notes Baseline (hit@6 3/5, MRR@6 ≈ 0.30) and experiment order; SC-004 status
note; PHRs 16–17. T032 8f5dcd8: 3 failing duplicate tests (same file, renamed copy, re-add
skips parse/embed). T033 6cba22c: add_paper computes the content ID first and returns
already_present via new store.paper_metadata(); contract updated. T034 ee06e33: checkpoint 3
duplicate section. T035 71d2b15: persistence test (passed immediately because T029 already
added per-folder caching and reset_cache; strengthened with new-collection and on-disk
assertions). T036 2a9fbd7: explicit library folder creation. T037 15fe94e: checkpoint 3
saves results to data/checkpoint3_last.json and checks them when run with no argument.
Checkpoint 3 (papers): duplicates PASS (223 → 223 passages) but search 2.485 s FAIL; the
first query after opening a persisted library loads the index (measured 0.635 s cold vs
0.036–0.041 s warm in a separate run). Persistence run PASS.

## Outcome

- ✅ Impact: US2 and US3 implemented; MVP (US1–US3) functionally complete.
- 🧪 Tests: 175 passed; persistence PASS; checkpoint 3 papers run FAIL on cold search timing.
- 📁 Files: library.py, store.py, checkpoint_3_search.py, test_library.py, contract, tasks, spec, probe notes.
- 🔁 Next prompts: decide how checkpoint 3 times search (warm-up query like the model load); then US4.
- 🧠 Reflection: SC-011 timing must separate one-time index load from per-search cost, as SC-010 does for the model.

## Evaluation notes (flywheel)

- Failure modes observed: cold vector-index load counted as search time; persistence test was not red first.
- Graders run and results (PASS/FAIL): pytest PASS; checkpoint 3 papers FAIL (timing); persistence PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): run one untimed warm-up search before the timed one and print the cold time separately.
