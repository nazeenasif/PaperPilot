---
id: 8
title: Analyze Feature 4 artifacts
stage: misc
date: 2026-10-25
surface: agent
model: claude-opus-5-5
feature: 004-summaries-comparison
branch: 004-summaries-comparison
user: Nazeen Asif
command: /sp.analyze
labels: ["analysis", "consistency", "coverage"]
links:
  spec: specs/004-summaries-comparison/spec.md
  ticket: null
  adr: history/adr/0008-per-part-grounding-and-structured-output.md, history/adr/0009-saved-results-and-multi-request-runs.md
  pr: null
files:
 - none modified (read-only analysis)
tests:
 - none
---

## Prompt

/sp.analyze Also confirm: (1) the two ADRs (per-part-grounding-and-structured-output, saved-results-and-multi-request-runs) exist; (2) research.md and docs/known-limitations.md record that the TL;DR check cannot catch a non-numeric claim with a valid citation, assigned to the evaluation feature.

## Response snapshot

**Confirmed:**
- ADR-0008 and ADR-0009 exist in history/adr/ (commit 1f7ca3d).
- research.md R3 (lines 99–108) and docs/known-limitations.md (line 156) both record the TL;DR blind spot (the F1 pattern), assigned to the evaluation feature's faithfulness judge.

**Findings:** 12 (0 critical, 3 high, 5 medium, 4 low). All 27 FRs are covered: 26 by tasks, and FR-006 by research R10.

High:
- **C1:** the relevance threshold (0.58, calibrated on questions' top scores) is applied to fixed facet and aspect queries without measurement. It could mark most sections not reported.
- **I1:** for a stale saved summary, the engine contract says `summarize` "otherwise generates" while T011 expects it to return the stale result.
- **U1:** it is unspecified whether a regeneration that ends with stopped or failed parts replaces a fully verified saved summary.

Medium:
- **U2:** the pre-check uses the plan's maximum even when a POST would reuse a saved result.
- **U3:** the TL;DR number check does not say how citation markers are excluded.
- **G1:** no task covers a paper deleted mid-run.
- **G2:** no contrast check for the new screens.
- **I2:** the docs/design images are outdated and uncommitted.

Low:
- **G3:** "after a restart" (SC-003) is not exercised.
- **I3:** the save-timing wording in research R6 is inconsistent.
- **I4:** some task labels and references are off.
- **T1:** Data vs Datasets naming (intentional).

Constitution: no violations; VII ⚠ justified (eval harness deferred).

## Outcome

- ✅ Impact: gaps found before implementation; nothing blocks, but C1, I1 and U1 should be fixed first.
- 🧪 Tests: none.
- 📁 Files: none modified.
- 🔁 Next prompts: approve remediation edits (spec/plan/tasks), then /sp.implement.
- 🧠 Reflection: the biggest risk is a calibration carried over from questions to a different kind of query.

## Evaluation notes (flywheel)

- Failure modes observed: none in the run.
- Graders run and results (PASS/FAIL): coverage 100% of FRs; constitution PASS.
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): measure facet-query top scores (0 requests) before T008.
