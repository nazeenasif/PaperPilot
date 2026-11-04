---
id: 10
title: Output limits, TL;DR dependency, facet probe
stage: green
date: 2026-11-04
surface: agent
model: claude-opus-5-5
feature: 004-summaries-comparison
branch: 004-summaries-comparison
user: Nazeen Asif
command: follow-up to the checkpoint 7 run
labels: ["output-budget", "tldr-dependency", "retrieval-probe", "faithfulness"]
links:
  spec: specs/004-summaries-comparison/spec.md
  ticket: null
  adr: history/adr/0008-per-part-grounding-and-structured-output.md, history/adr/0009-saved-results-and-multi-request-runs.md
  pr: null
files:
 - paperpilot/llm.py
 - paperpilot/service.py
 - scripts/checkpoint_7_summaries.py
 - scripts/probe_facets.py
 - eval/facet_probe.md
 - eval/probe_notes.md
 - frontend/components/summary/SummaryView.tsx
 - frontend/components/summary/TldrCard.tsx
 - frontend/lib/errorKinds.ts
 - frontend/lib/useSummary.ts
 - frontend/lib/types.ts
 - specs/004-summaries-comparison/spec.md
 - specs/004-summaries-comparison/research.md
 - specs/004-summaries-comparison/plan.md
 - specs/004-summaries-comparison/data-model.md
 - specs/004-summaries-comparison/contracts/engine-api.md
 - history/adr/0008-per-part-grounding-and-structured-output.md
 - history/adr/0009-saved-results-and-multi-request-runs.md
tests:
 - tests/test_llm_budget.py
 - tests/test_summarize_dependency.py
 - frontend/tests/tldr-dependency.test.tsx
---

## Prompt

Decision: raise the output limit, keep reasoning effort as is (the reasoning-effort experiment stays in the evaluation feature).

1. Make max_tokens configurable per task kind: answers stay 2048; summary sections, TL;DR and comparison cells get 4096. First check the model's maximum completion tokens in OpenRouter's model list and stay within it. Fake-client tests first. Amend ADR-0008 and research R5 with the measured reasoning lengths (943–1,679 tokens per summary part).
2. TL;DR dependency: record which sections a TL;DR was built from. When a section is regenerated, the TL;DR is marked "built without <section>" until it is regenerated too.
3. Facet retrieval probe, 0 requests: for all 5 papers × 5 facets, search with the current facet queries (k=4) and report which sections the passages come from. Mark where a facet's passages miss the obvious sections (Problem: Abstract/Introduction; Limitations: Limitations/Conclusion/Discussion). Don't change the queries yet; show me the table.
4. Record F2's third occurrence in eval/probe_notes.md: TL;DR claim 2, built from a Results section that had scoped the claim correctly. All three F2 cases came from combining sources.
Commit each separately and stop. No real model requests.

## Response snapshot

1. `llm.OUTPUT_TOKENS` with `generate(..., task=...)`: answers 2048; summary sections, TL;DR and comparison calls 4096. OpenRouter lists 65,536 max completion tokens for the free model (read from the public list, no key sent). Fake-client tests first. ADR-0008 and R5 amended. 4096 is unverified until a real run, and Method's true need is unknown.
2. The TL;DR records `built_from` and `built_without`. To make the mark possible, a section retry now reruns only that section (1 request) and the TL;DR is retried separately (1 request), which amends FR-020 and ADR-0009. The UI shows "Built without Method." with Rewrite the TL;DR and withholds "All citations verified". Saved summaries get the values from their section states, so the LoRA summary now reads built without Method.
3. `scripts/probe_facets.py` and `eval/facet_probe.md`: Problem misses its obvious sections in 4 of 5 papers (Lost in the Middle 1/4); Limitations misses in 4 of 5 (RAG 1/4). Every paper has an Abstract and Introduction, and each has a Conclusion or Discussion. Queries unchanged.
4. F2's third occurrence recorded. probe_notes.md held only one F2 case, so a second was added: the checkpoint 6 answer of 2026-10-25, with its provenance stated. The researcher should confirm it is the intended one.

Tests: pytest 674; Vitest 177; Playwright F4 tests 6 passed. Model requests: 0 (provider count 6 before and after the probe).

## Outcome

- ✅ Impact: per-task limits in place; TL;DR dependency visible; retrieval weakness measured.
- 🧪 Tests: see above.
- 📁 Files: see the list above.
- 🔁 Next prompts: decide on the facet queries; retry Method then the TL;DR (2 requests) to test 4096.
- 🧠 Reflection: a "Limitations" miss is not always a wrong result: LoRA's stated limitation is in Our Method, so the marks point at where to look rather than prove a fault.

## Evaluation notes (flywheel)

- Failure modes observed: the requested mark was unreachable under automatic TL;DR rewriting; the notes recorded fewer F2 cases than the request assumed.
- Graders run and results (PASS/FAIL): pytest PASS; vitest PASS; playwright F4 PASS.
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): retry Method and the TL;DR with the 4096 limit.
