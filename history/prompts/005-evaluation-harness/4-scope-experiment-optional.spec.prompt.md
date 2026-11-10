---
id: 4
title: Make the scope experiment optional
stage: spec
date: 2026-11-11
surface: agent
model: claude-opus-5-5
feature: 005-evaluation-harness
branch: 005-evaluation-harness
user: Nazeen Asif
command: follow-up to /sp.specify
labels: ["evaluation", "scope-rule", "faithfulness", "request-budget"]
links:
  spec: specs/005-evaluation-harness/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/005-evaluation-harness/spec.md
 - specs/004-summaries-comparison/research.md
tests:
 - none
---

## Prompt

Scope-rule experiment: optional, like reasoning effort and the second model. If run, it uses at least 3 runs per condition (rule on / off) on the fixed set, and reports F2-type verdicts per run, not a single average. Until then, research R3 records the current evidence: the TL;DR F2 pattern did not recur in the two runs since the rule was added, but the comparison's "TriviaQA not used" dropped its scope with the rule on. The rule stays enabled (low risk) and is marked "unmeasured".

## Response snapshot

FR-024a makes the scope rule optional. FR-025, FR-025a and FR-025b require at least 3 runs per condition stored separately, with F2-type verdicts per run. Research R3 of Feature 4 records the evidence and the status unmeasured. Three runs have had the rule on: v3 had Results cut off, so "two runs" is stated as the two that had a Results section. v4's Data claim 9, also a loss of scope with the rule on, is added beside TriviaQA.

## Outcome

- ✅ Impact: required spend falls to about 170 requests (about 95 if the baseline wins).
- 🧪 Tests: none (specification).
- 📁 Files: see the list above.
- 🔁 Next prompts: /sp.plan.
- 🧠 Reflection: repeated runs need their own cache identity, or the cache would return the first run three times.

## Evaluation notes (flywheel)

- Failure modes observed: none.
- Graders run and results (PASS/FAIL): specification checklist 16 of 16.
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
