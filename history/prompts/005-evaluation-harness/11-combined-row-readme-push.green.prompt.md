---
id: 11
title: Combined row, README and push
stage: green
date: 2026-11-13
surface: agent
model: claude-opus-5-5
feature: 005-evaluation-harness
branch: 005-evaluation-harness
user: Nazeen Asif
command: none
labels: ["evaluation", "retrieval", "readme", "push"]
links:
  spec: specs/005-evaluation-harness/spec.md
  ticket: null
  adr: history/adr/0012-retrieval-experiments-and-gate.md
  pr: https://github.com/nazeenasif/PaperPilot/compare/main...005-evaluation-harness
files:
 - evaluation/experiments.py
 - evaluation/retrieval.py
 - evaluation/report.py
 - evaluation/__main__.py
 - eval/experiments.json
 - eval/results/prefix-hybrid.json
 - eval/results.md
 - README.md
 - specs/005-evaluation-harness/spec.md
 - specs/005-evaluation-harness/tasks.md
tests:
 - tests/evaluation/test_combined.py
 - tests/evaluation/test_experiments.py
 - tests/evaluation: 105 passed
---

## Prompt

I've reviewed the 12 questions and the table. Approved.

1. Run one more free row: prefix + hybrid combined (0 requests), so we can see if the two best ideas add up.
2. Update the README's one-line description to: "PaperPilot: an AI research assistant that answers questions about research papers with verified citations that open the exact PDF passage."
3. Use this overall conclusion above the table: "Adding the paper title and section to each passage before embedding gave the best ranking (MRR 0.31 → 0.41, hit@1 0.20 → 0.30) at no runtime cost. Off-the-shelf rerankers found more answers within the top 10 but ranked them lower, and were 2–20× slower. With 10 answerable questions, these are indicative results."
4. Push 005-evaluation-harness and give me the compare link against main. Stop.

## Response snapshot

The combined row changes two settings from the baseline, so experiments may now name an earlier `base` row and change one setting from it (FR-023 amended; T031a tests, T031b implementation). prefix-hybrid: hit@1 0.200, hit@6 0.700, hit@10 0.800, MRR 0.425, 0.15 s/question, 0 requests; the best hit@6 and MRR of any row. README description and the conclusion (verbatim, from eval/experiments.json) added; report regenerated. Branch pushed; compare link given.

## Outcome

- ✅ Impact: six retrieval rows, conclusion and README published on the branch.
- 🧪 Tests: tests/evaluation 105 passed.
- 📁 Files: listed above.
- 🔁 Next prompts: open the PR; possibly revise the conclusion for the combined row.
- 🧠 Reflection: the dictated conclusion predates the combined row, which now has the best MRR (0.425 > 0.407).

## Evaluation notes (flywheel)

- Failure modes observed: a hard-coded experiment count in a test (now 9).
- Graders run and results (PASS/FAIL): pytest PASS; golden check PASS.
- Prompt variant (if applicable): none.
- Next experiment (smallest change to try): none.
