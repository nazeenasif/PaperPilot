---
id: 1
title: Specify summaries and comparison
stage: spec
date: 2026-10-25
surface: agent
model: claude-opus-5-5
feature: 004-summaries-comparison
branch: 004-summaries-comparison
user: Nazeen Asif
command: /sp.specify
labels: ["summaries", "comparison", "grounding", "caching", "request-budget"]
links:
  spec: specs/004-summaries-comparison/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/004-summaries-comparison/spec.md
 - specs/004-summaries-comparison/checklists/requirements.md
tests:
 - none (specification only)
---

## Prompt

/sp.specify Feature 4: Paper summaries and cross-paper comparison for PaperPilot (see docs/paperpilot-guide.pdf, Phase 6), built into the existing web app. Visual style: docs/design/ (dark cinematic). Every grounding rule from Features 2–3 applies: citations validated in code, not-found instead of guessing, nothing unverified shown as verified.

User stories:
1. As a researcher, I click "Summarize" on a paper and get a structured summary: a short TL;DR plus five sections (problem, method, data, results, limitations), each with its own citations that open the PDF at the cited page with the highlight.
2. As a researcher, I open a summary I generated before and it appears instantly, without spending model requests; I can choose to regenerate it.
3. As a researcher, I select 2–4 papers and aspects (default: problem, method, datasets, results, limitations) and get a comparison table where every cell carries its own citations.
4. As a researcher, when a section or cell isn't supported by the retrieved passages, I see "Not reported in the retrieved passages" for that part only, while the rest is shown.
5. As a researcher, I see how many model requests a summary or comparison will cost before I start it, and the daily-limit and busy states work as they do for questions.

Functional requirements:
- Summaries are query-focused: one retrieval per facet within the paper, then one generation per facet; the TL;DR is generated from the verified sections and must itself carry citations to their passages (no uncited TL;DR).
- Comparison retrieves passages per paper and per aspect separately (so the paper with the most text can't dominate), de-duplicates and numbers them, and asks for a table with citations inside cells.
- Each summary section and each comparison cell is validated on its own: invalid citations → that part is held back with a warning; no citations → "Not reported"; the remainder stays visible.
- Results are cached per paper (summary) or per paper set and aspects (comparison), keyed so they are invalidated when the paper is re-processed or LLM_MODEL changes.
- Progress events stream per facet or aspect, as for questions; nothing unverified is shown before validation.
- The request cost is known before starting and counted by the shared request counter; a summary must stay within its planned requests plus retries.
- Long outputs must fit the model's output budget, remembering that reasoning tokens count against it; a cut-off output is an error for that part, never a truncated answer.

Out of scope: map-reduce summaries of every passage (document it as the rejected alternative), more than 4 papers per comparison, exporting summaries, the evaluation harness.

Acceptance criteria (guide Checkpoints 6–7):
- A summary of LoRA and a comparison of BERT and RAG on method, datasets and results are generated with all citations valid.
- I verify at least five claims from each against the PDFs by hand, recording for any wrong claim whether retrieval or the model was at fault.
- Re-opening the LoRA summary costs 0 model requests.
- A comparison cell the papers don't support shows "Not reported", not an invented value.
- Total real model requests for the checkpoints are planned and printed.

## Response snapshot

Created branch `004-summaries-comparison` and `specs/004-summaries-comparison/spec.md`. The guide PDF is not present locally (as the constitution notes), so the spec follows the description.

The spec defines five user stories:
- US1 (P1): a summary with cited sections.
- US2 (P1): a free reopen, plus regeneration.
- US3 (P2): a 2–4 paper comparison table.
- US4 (P1): per-part "Not reported" and held-back states.
- US5 (P2): the cost shown up front, and the daily-limit and busy states.

It also sets out:
- **Edge cases** and FR-001–FR-027.
- **Key entities**: Summary, Comparison, Part, Facet/Aspect, Request plan.
- **SC-001–SC-010**, assumptions, dependencies and out of scope. Map-reduce is recorded as the rejected alternative (FR-006).

Two clarifications were asked: FR-007 (a fixed list of aspects or typed ones) and FR-009 (one request per aspect or one per table). The checklist had 15 of 16 items passing pending those answers.

## Outcome

- ✅ Impact: Feature 4 specification drafted; two scope and cost questions raised.
- 🧪 Tests: none (specification).
- 📁 Files: spec.md, checklists/requirements.md.
- 🔁 Next prompts: answer Q1 and Q2, then /sp.plan.
- 🧠 Reflection: the request budget (about 50 a day) drives most of the design: cost shown up front, saved results, part-level retries.

## Evaluation notes (flywheel)

- Failure modes observed:
  - create-new-feature.ps1 created the branch and spec, then printed a parameter-binding error; it was not re-run.
  - The guide PDF is missing locally.
- Graders run and results (PASS/FAIL): spec quality checklist, 15/16 PASS (clarifications pending).
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
