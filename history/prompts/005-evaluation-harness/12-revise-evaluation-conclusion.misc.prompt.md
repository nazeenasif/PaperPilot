---
id: 12
title: Revise evaluation conclusion
stage: misc
date: 2026-11-13
surface: agent
model: claude-opus-5-5
feature: 005-evaluation-harness
branch: 005-evaluation-harness
user: Nazeen Asif
command: none
labels: ["evaluation", "readme", "conclusion"]
links:
  spec: specs/005-evaluation-harness/spec.md
  ticket: null
  adr: null
  pr: https://github.com/nazeenasif/PaperPilot/compare/main...005-evaluation-harness
files:
 - eval/experiments.json
 - eval/results.md
 - README.md
tests:
 - tests/evaluation/test_report.py, test_combined.py, test_experiments.py (31 passed)
---

## Prompt

Replace the conclusion with: "Adding the paper title and section to each passage before embedding gave the best single improvement (MRR 0.31 → 0.41, hit@1 0.20 → 0.30) at no runtime cost. Combined with hybrid BM25 + vector search, it reached hit@6 0.70 (baseline 0.40) and MRR 0.43. Off-the-shelf rerankers found more answers within the top 10 but ranked them lower, and were 2–20× slower. With 10 answerable questions, these are indicative results." Regenerate the report, commit, push, and stop.

## Response snapshot

Replaced the conclusion in eval/experiments.json verbatim, regenerated README.md and eval/results.md (0 model requests), committed 31d5913 and pushed 005-evaluation-harness.

## Outcome

- ✅ Impact: the README conclusion matches all six rows.
- 🧪 Tests: 31 passed.
- 📁 Files: listed above.
- 🔁 Next prompts: open the pull request.
- 🧠 Reflection: none.

## Evaluation notes (flywheel)

- Failure modes observed: none.
- Graders run and results (PASS/FAIL): pytest PASS.
- Prompt variant (if applicable): none.
- Next experiment (smallest change to try): none.
