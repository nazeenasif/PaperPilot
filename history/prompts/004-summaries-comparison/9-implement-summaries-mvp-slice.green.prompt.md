---
id: 9
title: Implement summaries MVP slice
stage: green
date: 2026-11-04
surface: agent
model: claude-opus-5-5
feature: 004-summaries-comparison
branch: 004-summaries-comparison
user: Nazeen Asif
command: /sp.implement
labels: ["summaries", "tldr-check", "saved-results", "part-states", "checkpoint-7", "output-budget"]
links:
  spec: specs/004-summaries-comparison/spec.md
  ticket: null
  adr: history/adr/0008-per-part-grounding-and-structured-output.md, history/adr/0009-saved-results-and-multi-request-runs.md
  pr: null
files:
 - paperpilot/prompts.py
 - paperpilot/service.py
 - paperpilot/library.py
 - api/routes.py
 - api/schemas.py
 - api/errors.py
 - scripts/checkpoint_7_summaries.py
 - frontend/app/summarize/page.tsx
 - frontend/app/summarize/[paperId]/page.tsx
 - frontend/components/summary/ (SummaryView, SummarizePicker, TldrCard, SectionCard, CitedText, CostButton, PartState)
 - frontend/components/app/Header.tsx
 - frontend/components/library/PaperCard.tsx
 - frontend/lib/useSummary.ts
 - frontend/lib/time.ts
 - frontend/lib/errorKinds.ts
 - frontend/lib/types.ts
 - frontend/vitest.config.ts
 - frontend/e2e/smoke.spec.ts
 - frontend/e2e/fake-backend.ts
 - frontend/e2e/fixtures.ts
 - specs/004-summaries-comparison/research.md
 - specs/004-summaries-comparison/tasks.md
 - docs/verification/checkpoint-7-2026-11-04.md
tests:
 - tests/test_grounding_parts.py, test_prompts_summary.py, test_summarize.py, test_results_cache.py, test_summarize_saved.py, test_summarize_states.py
 - tests/api/test_summaries_api.py
 - frontend/tests/navigation.test.tsx, summary.test.tsx, summarize-picker.test.tsx, part-states.test.tsx
 - frontend/e2e/smoke.spec.ts "F4 US1 summary", "F4 US2 reopen", "F4 US4 part states"
 - scripts/checkpoint_7_summaries.py summary reopen (6 real requests)
---

## Prompt

/sp.implement the MVP slice: T001–T014, T021–T026, T031–T032, T034–T044. Tests first, one commit per task. Then run checkpoint 7's summary and reopen parts only (6 planned requests), show the summary with every claim and its passage, and stop.

## Response snapshot

All 33 tasks are done, one commit each.

Tests written after the behaviour existed passed at once and were checked with mutation runs: T013 (6 of 11 failed when mutated) and T025. T014 and T026 are no-code commits that say so.

Analysis findings handled inside the slice:
- C1: facet-query scores measured, all clear 0.58 on the five papers.
- I1: a stale summary is returned marked stale, never regenerated silently.
- U1: a regeneration ending with failed parts keeps a complete saved summary.
- U3: citation markers are excluded from the TL;DR number check.

Not handled: U2 and the before-stream daily-limit check (US5, outside the slice).

The cache key is the identity (kind, papers, aspects); model, version and fingerprints are stored beside it and compared on lookup, because hashing them in would make stale results unfindable. This differs from research R6's wording.

Checkpoint 7 `summary reopen`: 6 requests (6 planned, 0 retries; cap 12), **overall FAIL**.
- Method was cut off at the 2,048-token cap, so 5 of 6 parts are verified. Nothing truncated was shown, and the other parts stayed.
- Shown citations valid: PASS. Cited passages open at their page, 10/10: PASS.
- Reopen in 63 ms: PASS. The log shows no model call after the summary; the provider's "5 → 5" was lag, and it read 6 afterwards.
- 14 claims written to docs/verification/checkpoint-7-2026-11-04.md; the hand check is the researcher's.

Corrections made after the run:
- The checkpoint double-counted tokens (output already includes reasoning). It now reports the true figures and fails on a cut-off part. The run itself was not repeated.
- Research R5's headroom claim was wrong. Measured reasoning was 943-1,679 tokens per call against 220-510 assumed; output used 1,018-1,925 of 2,048.

Test fixes along the way:
- "server unreachable" used route.fallback(), which reached a real API on port 8000; it now uses the fixture.
- Two navigation waits and Vitest's per-test limit were raised for slow runs under load.
- One test race on the usage figure was fixed.

Final test runs: pytest 655; Vitest 173 (three clean runs); Playwright 31 passed, 1 skipped by design, against an already-compiled dev server. A cold dev server failed 5 tests on first-compile timeouts with about 0.5-1.4 GB of memory free. The ask() tests have no commits since T004.

## Outcome

- ✅ Impact: the MVP works end to end; the checkpoint's failure is a real output-budget problem on the free model.
- 🧪 Tests: see above.
- 📁 Files: see the list above.
- 🔁 Next prompts: decide how to give reasoning room (LLM_REASONING_EFFORT=low or a higher cap), retry Method (2 requests), hand-check the claims, then US3, US5 and Polish.
- 🧠 Reflection: Feature 2's reasoning figures did not carry over to section prompts; measuring tokens per part caught it. The Problem section drew all four passages from section 7, which looks like a retrieval weakness for the hand check to confirm.

## Evaluation notes (flywheel)

- Failure modes observed: output cut off by reasoning; double-counted tokens in the checkpoint; a test depending on a running API; first-compile timeouts under low memory; ADR-0008's "far below" the cap is contradicted by the measurement and has not been amended.
- Graders run and results (PASS/FAIL): pytest PASS; vitest PASS; playwright PASS (warm server); checkpoint 7 FAIL (Method cut off).
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): re-run Method with LLM_REASONING_EFFORT=low and compare tokens and faithfulness.
