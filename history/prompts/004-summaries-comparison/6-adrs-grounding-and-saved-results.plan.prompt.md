---
id: 6
title: ADRs grounding and saved results
stage: plan
date: 2026-10-25
surface: agent
model: claude-opus-5-5
feature: 004-summaries-comparison
branch: 004-summaries-comparison
user: Nazeen Asif
command: /sp.adr
labels: ["adr", "grounding", "structured-output", "cache", "request-budget"]
links:
  spec: specs/004-summaries-comparison/spec.md
  ticket: null
  adr: history/adr/0008-per-part-grounding-and-structured-output.md, history/adr/0009-saved-results-and-multi-request-runs.md
  pr: null
files:
 - history/adr/0008-per-part-grounding-and-structured-output.md
 - history/adr/0009-saved-results-and-multi-request-runs.md
 - specs/004-summaries-comparison/plan.md
tests:
 - none (documentation)
---

## Prompt

/sp.adr per-part-grounding-and-structured-output
/sp.adr saved-results-and-multi-request-runs

## Response snapshot

Created two ADRs from the Feature 4 plan. No `create-adr` script exists in `.specify/`, so the ADRs were written from the template, in the format of ADR-0001 to ADR-0007.

**ADR-0008, Per-Part Grounding and Structured Output** (extends ADR-0004):
- One validator, scoped by the passage numbers allowed for each part.
- Shared `format_passages` and `number_passages`; the five part states.
- The TL;DR checked in code, with four rules.
- JSON comparison rows parsed by a tolerant parser; a malformed row is retryable.
- A per-part output budget.

Alternatives: whole-output validation, a separate validator, markdown tables, provider JSON mode, and other TL;DR checks. The F1 blind spot is listed as a negative consequence.

**ADR-0009, Saved Results and Multi-Request Runs** (extends ADR-0007):
- SQLite `results.sqlite3`, keyed by paper IDs, passage fingerprints, aspects, prompt version and model.
- Explicit invalidation on delete or re-process, plus a staleness check on lookup.
- Reopening costs 0 requests; regeneration replaces the old result only on completion; part retries.
- A request plan with a pre-check, stop rules, and a shared `model_lock` (`busy_task`).

Alternatives: JSON files, ChromaDB metadata, an in-memory cache, other key choices, an exact pre-computed plan, continuing past a busy model, separate locks, and map-reduce.

Both pass the significance test and the grader (clustered; alternatives with rationale; positive and negative consequences; references). No conflicts with existing ADRs. plan.md's candidates list is replaced by links to both ADRs.

## Outcome

- ✅ Impact: Feature 4's two architectural decision clusters are recorded.
- 🧪 Tests: none (documentation).
- 📁 Files: ADR-0008, ADR-0009, plan.md.
- 🔁 Next prompts: /sp.tasks.
- 🧠 Reflection: both ADRs amend earlier ones rather than replacing them, which keeps the decision history readable.

## Evaluation notes (flywheel)

- Failure modes observed: the `create-adr` script is missing; ADRs were written agent-natively.
- Graders run and results (PASS/FAIL): ADR checklist PASS for both (clustered, alternatives, pros and cons, concise).
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
