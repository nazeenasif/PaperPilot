---
id: 6
title: ADRs for harness, judge and retrieval
stage: plan
date: 2026-11-11
surface: agent
model: claude-opus-5-5
feature: 005-evaluation-harness
branch: 005-evaluation-harness
user: Nazeen Asif
command: /sp.adr
labels: ["adr", "evaluation", "judge", "retrieval"]
links:
  spec: specs/005-evaluation-harness/spec.md
  ticket: null
  adr: history/adr/0010-evaluation-harness-architecture.md, history/adr/0011-llm-judge-and-calibration.md, history/adr/0012-retrieval-experiments-and-gate.md
  pr: null
files:
 - history/adr/0010-evaluation-harness-architecture.md
 - history/adr/0011-llm-judge-and-calibration.md
 - history/adr/0012-retrieval-experiments-and-gate.md
 - specs/005-evaluation-harness/plan.md
tests:
 - none
---

## Prompt

/sp.adr evaluation-harness-architecture
/sp.adr llm-judge-and-calibration
/sp.adr retrieval-experiments-and-gate

## Response snapshot

Three ADRs created by hand, Proposed: 0010 evaluation harness architecture, 0011 LLM judge and calibration, 0012 retrieval experiments and the relevance gate. The repository has no create-adr script (no `.specify/scripts/bash/`, and none among the PowerShell scripts), so the template's format and the next numbers were followed. Each passes the grader: clustered decisions, explicit alternatives, positive and negative consequences, and references. No conflicts: 0010 extends ADR-0003 and ADR-0007, and 0012 keeps ADR-0004's gate. The plan's ADR section now links them.

## Outcome

- ✅ Impact: the harness's three significant decisions are recorded before tasks.
- 🧪 Tests: none.
- 📁 Files: see the list above.
- 🔁 Next prompts: /sp.tasks.
- 🧠 Reflection: the gate decision is the one most likely to be questioned when a reranker wins, so its trade-off is explicit.

## Evaluation notes (flywheel)

- Failure modes observed: create-adr.sh is missing from the repository.
- Graders run and results (PASS/FAIL): ADR checklist PASS for all three.
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
