---
id: 1
title: Specify the evaluation harness
stage: spec
date: 2026-11-11
surface: agent
model: claude-opus-5-5
feature: 005-evaluation-harness
branch: 005-evaluation-harness
user: Nazeen Asif
command: /sp.specify
labels: ["evaluation", "golden-set", "judge", "experiments", "request-budget"]
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

/sp.specify Feature 5: Evaluation harness for PaperPilot (see docs/paperpilot-guide.pdf, Phases 11–12). Goal: measure retrieval and answer quality on a fixed golden set, so every change is judged by numbers, and produce the results table for the README.

User stories:
1. As the developer, I maintain a golden set of 30–50 questions over the 5 papers: answerable single-paper questions, cross-paper questions, near-miss and off-topic questions (expected: not-found), and multi-turn follow-ups. Each answerable question records its expected answer and evidence phrase(s) with paper and page, never passage IDs (IDs change when chunking changes).
2. As the developer, I run retrieval evaluation (hit@k, MRR) with zero model requests, for any retrieval configuration.
3. As the developer, I run answer evaluation: each answer is checked for citation validity, correct refusal, and faithfulness by an LLM judge; answers and judge verdicts are cached so re-running the judge or the report costs nothing.
4. As the developer, I trust the judge because it is calibrated against my own hand verdicts (docs/verification reports and eval/probe_notes.md cases F1, F2, F3), with agreement reported, and every judge verdict shows the claim and passage it judged.
5. As the developer, I run experiments one variable at a time and get one row per experiment in a results table (hit@6, MRR, faithfulness, correct refusals, latency, requests), with a written takeaway.

Requirements:
- Experiments to support: baseline; cross-encoder reranking of the top 20 (local, free); hybrid BM25 + vector; title/section prefix before embedding; the scope rule on/off; LLM_REASONING_EFFORT low vs default; a second model (google/gemma-4-31b-it:free).
- The known cases are fixed test items: F1 (misattribution), F2 (scope extension, 4+ occurrences), F3 (wrong-item number, 3 runs), Q2/Q4 false not-founds, the LoRA/BERT summary and comparison flags.
- Request budget: every run plans its requests up front, refuses to start without enough remaining, and can resume across days; retrieval-only runs cost 0. The judge should be a different model from the answerer where possible, to avoid self-grading.
- The judge sees only the claim and its cited passages, and outputs structured verdicts (supported / partly / unsupported, with the reason).
- Results are stored per experiment with the exact configuration (model, prompt versions, chunking, retrieval settings), so rows are reproducible.

Out of scope: new user-facing features, RAGAS integration, fine-tuning.

Acceptance criteria (guide Checkpoint 11):
- A golden set with a baseline row and at least two experiments with written conclusions.
- Judge agreement with my hand verdicts is reported, with disagreements listed.
- The README results table is generated from stored results, not typed by hand.

## Response snapshot

Branch 005-evaluation-harness, spec and checklist written. Six stories (the request budget split out), 30 functional requirements, 10 success criteria. The guide's Phases 11 and 12 were read. Two questions are open: FR-012, one judge request per claim or per answer; FR-025, what the scope-rule experiment runs on, since the rule is not in the answer instructions. Calibration requires both supported and unsupported hand verdicts (FR-022), because the recorded cases are all failures and the reports' Verdict columns are empty. The feature script failed after creating the spec, on a Join-Path call Windows PowerShell 5.1 does not support; it was not rerun.

## Outcome

- ✅ Impact: Feature 5 specified, pending two answers.
- 🧪 Tests: none (specification).
- 📁 Files: see the list above.
- 🔁 Next prompts: answer FR-012 and FR-025, then /sp.plan.
- 🧠 Reflection: the scope-rule experiment as described could not have shown anything on the golden questions, because answers never use that rule.

## Evaluation notes (flywheel)

- Failure modes observed: create-new-feature.ps1 fails at its prompts folder under Windows PowerShell 5.1.
- Graders run and results (PASS/FAIL): specification checklist 15 of 16, the open item being the two clarifications.
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
