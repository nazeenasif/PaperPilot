---
id: 4
title: Plan summaries and comparison
stage: plan
date: 2026-10-25
surface: agent
model: claude-opus-5-5
feature: 004-summaries-comparison
branch: 004-summaries-comparison
user: Nazeen Asif
command: /sp.plan
labels: ["plan", "grounding", "tldr-check", "json-rows", "results-cache", "request-budget"]
links:
  spec: specs/004-summaries-comparison/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/004-summaries-comparison/plan.md
 - specs/004-summaries-comparison/research.md
 - specs/004-summaries-comparison/data-model.md
 - specs/004-summaries-comparison/contracts/engine-api.md
 - specs/004-summaries-comparison/contracts/web-api.md
 - specs/004-summaries-comparison/quickstart.md
tests:
 - none (planning)
---

## Prompt

Exported. Please check the three images as you described, commit them with the spec, checklist and PHR, then run /sp.plan for 004-summaries-comparison.

Plan priorities:
- Reuse ask()'s pipeline: retrieval, prompt building, marker stripping, citation validation, the request counter and progress events. No second copy of grounding logic.
- TL;DR check: its citations must be a subset of the verified sections' citations, and each TL;DR sentence must be traceable to one of those sections. Explain how this is checked in code and what happens on failure (TL;DR held back; sections still shown).
- Comparison: per aspect, retrieve per paper separately; ask for structured JSON output (one object per paper cell) rather than a markdown table, and validate each cell on its own. Handle malformed JSON as a failed row with a retry, never a crash.
- Cache: SQLite, keyed by paper content IDs, aspect, prompt version and LLM_MODEL; invalidated on re-process or delete.
- Output budget: each call must fit max_tokens including reasoning tokens; a cut-off part is an error for that part only.
- Checkpoint 7: LoRA summary and BERT vs RAG comparison, planned requests printed, every claim listed with paper, page and passage for my hand check.

Suggest which decisions deserve ADRs.

## Response snapshot

**Design images**: not committed. The files in docs/design/ (and the only other copies, in Downloads) are unchanged: same sizes and timestamps (12:46:45), and compare.png still reads "uses 1 request". The spec, checklist and PHR 3 were committed without them (2718033).

**Plan** (plan.md, research R1–R11, data-model.md, contracts, quickstart.md):
- **R1, one pipeline:** `check_citations` and `review_reply` gain an `allowed` set of passage numbers. `format_passages` is shared, and `number_passages` keeps one number per passage. `ask()` behaviour is unchanged.
- **R2, facets:** five fixed facets with 4 passages each. Below the threshold a facet is not reported, with no request.
- **R3, TL;DR:** generated from verified sections only, then checked in `prompts.check_tldr`:
  - (1) not-found means not reported;
  - (2) every sentence must cite;
  - (3) citations must be a subset of the verified sections' citations;
  - (4) every number in a sentence must appear in the sections it traces to.

  Failure holds back the TL;DR only; the sections stay shown. With no verified sections there is no request and the TL;DR is not reported.
- **R4, comparison rows:** one request per aspect, retrieval per paper (3 each), JSON cells. The tolerant `parse_row` treats a malformed reply as a failed row that can be retried. Each cell is validated against its own paper's passage numbers.
- **R5, output budget:** word limits keep every call far below the 2048-token cap, reasoning included. A cut-off is a failure of that part only.
- **R6, cache:** SQLite `results.sqlite3`, keyed by paper IDs, passage fingerprints, aspects, prompt version and model. Results are forgotten on delete or re-process. Stale results stay readable but are never shown as current.
- **R7:** no new module.
- **R8, run control:** the plan is known before start, with a pre-check against remaining requests. Runs stop on systemic failures. A shared model lock replaces `busy_question` with `busy_task`.
- **R10:** map-reduce rejected.
- **R11, checkpoint 7:** plan 10 requests (cap 20), with a claims list written to `docs/verification/`.

The Constitution Check passes. VII is ⚠, justified: the eval harness stays deferred, as in Feature 2.

ADR candidates: per-part grounding and the TL;DR check; structured JSON rows; the saved-results cache; run control. The last two could be grouped.

The agent-context script only added a BOM to CLAUDE.md (no technology section exists), so that change was reverted.

## Outcome

- ✅ Impact: a complete design for Feature 4 that reuses the grounding pipeline.
- 🧪 Tests: none (planning).
- 📁 Files: plan.md, research.md, data-model.md, contracts/engine-api.md, contracts/web-api.md, quickstart.md.
- 🔁 Next prompts: /sp.adr for the chosen candidates, then /sp.tasks.
- 🧠 Reflection: the paper ID is a hash of the PDF bytes, so re-processing keeps the same ID. Cache invalidation therefore needs explicit hooks, not just the key.

## Evaluation notes (flywheel)

- Failure modes observed:
  - The design re-export did not reach the project folder.
  - update-agent-context.ps1 made a BOM-only edit.
- Graders run and results (PASS/FAIL): Constitution Check PASS (VII ⚠ justified).
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
