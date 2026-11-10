---
id: 2
title: Clarify judge requests and scope experiment
stage: spec
date: 2026-11-11
surface: agent
model: claude-opus-5-5
feature: 005-evaluation-harness
branch: 005-evaluation-harness
user: Nazeen Asif
command: answers to the /sp.specify questions
labels: ["evaluation", "judge", "scope-rule", "clarification"]
links:
  spec: specs/005-evaluation-harness/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/005-evaluation-harness/spec.md
 - specs/005-evaluation-harness/checklists/requirements.md
tests:
 - none
---

## Prompt

Q1: Custom: B (one request per claim) for judge calibration; A (one request per answer) for experiments.
Q2: Custom: LoRA and BERT summaries plus the BERT–RAG comparison, rule on vs off. Reuse existing saved rule-on outputs where their stored configuration matches exactly. Record that one run per condition gives an indicative result only, since F2 doesn't occur in every run.

## Response snapshot

FR-012 now makes one judge request per claim for calibration and one per answer, summary part or comparison row for experiments. FR-025, FR-025a and FR-025b set the fixed set, the reuse of saved rule-on outputs and the indicative-only statement. Clarifications recorded; all 16 checklist items pass. Saved outputs do not record reasoning effort or output limit, so the spec states how reuse treats those two.

## Outcome

- ✅ Impact: the spec has no open questions and is ready for planning.
- 🧪 Tests: none (specification).
- 📁 Files: see the list above.
- 🔁 Next prompts: /sp.plan; the researcher's hand verdicts for calibration.
- 🧠 Reflection: "matches exactly" can only compare what saved outputs recorded, so the gap had to be stated.

## Evaluation notes (flywheel)

- Failure modes observed: none.
- Graders run and results (PASS/FAIL): specification checklist 16 of 16.
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
