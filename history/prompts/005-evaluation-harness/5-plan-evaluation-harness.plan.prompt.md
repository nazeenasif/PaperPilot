---
id: 5
title: Plan the evaluation harness
stage: plan
date: 2026-11-11
surface: agent
model: claude-opus-5-5
feature: 005-evaluation-harness
branch: 005-evaluation-harness
user: Nazeen Asif
command: /sp.plan
labels: ["evaluation", "reranker", "hybrid-search", "judge", "calibration", "request-budget"]
links:
  spec: specs/005-evaluation-harness/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/005-evaluation-harness/plan.md
 - specs/005-evaluation-harness/research.md
 - specs/005-evaluation-harness/data-model.md
 - specs/005-evaluation-harness/quickstart.md
 - specs/005-evaluation-harness/contracts/cli.md
 - specs/005-evaluation-harness/contracts/engine-api.md
tests:
 - none
---

## Prompt

/sp.plan Plan Feature 5 (005-evaluation-harness). Research and justify:
- Golden set format: a versioned file (YAML or JSON) with question, type, expected answer, and evidence phrases with paper and page. Evidence is matched to passages by normalised text (same cleaning as ingest, tolerant of hyphen joins and re-chunking), never by passage ID. Include a validator that fails if an evidence phrase matches no passage.
- Retrieval metrics: hit@k and MRR computed per question type; local, 0 requests.
- Reranker: a local cross-encoder over the top 20. Compare candidates by size, CPU latency per question and licence; verify current versions before pinning.
- Hybrid: BM25 (rank-bm25) fused with vector scores; justify the fusion method (e.g. reciprocal rank fusion) and its parameter.
- Title/section prefix: requires re-embedding into a separate library directory, so the baseline library is never modified.
- Judge: a different free model from the answerer, verified on OpenRouter's current free list; structured verdicts (supported / partly / unsupported, reason); cached by claim, passages, judge model and judge prompt version.
- Calibration: hand verdicts stored in a file, the agreement metric, and how disagreements are listed.
- Sessions: request slices, the reserve, resume across days.
- Results: stored per experiment with full configuration; the README results table is generated from them.
Suggest which decisions deserve ADRs.

## Response snapshot

Plan, research R1–R12, data model, two contracts and quickstart written. Golden set as JSON, papers by arXiv ID, evidence matched by normalised, hyphen-insensitive text, with a validator for passage and page. Cross-encoders timed on this CPU: MiniLM-L6-v2 at 2.0 s per question (chosen, revision 233902d25c44), TinyBERT-L2 at 0.16 s as a second row, L12 at 5.8 s; the larger ones not measurable here; jina excluded for its licence. rank-bm25 0.2.2 with reciprocal rank fusion, k = 60, as published. The gate stays on the vector score. Judge gemma-4-31b-it:free, verified on today's free list. Kappa and per-label agreement for calibration. A separate `evaluation` package, recorded in Complexity Tracking. Three ADRs suggested. The agent-context script only added a byte-order mark to CLAUDE.md, so that was reverted.

## Outcome

- ✅ Impact: the harness is designed with 0-request retrieval first and one new dependency.
- 🧪 Tests: none (planning); reranker timings measured locally with 0 model requests.
- 📁 Files: see the list above.
- 🔁 Next prompts: /sp.adr for the three suggestions; /sp.tasks.
- 🧠 Reflection: the guide's reranker name `ms-marco-MiniLM-L-6-v2` no longer resolves; the current one is `ms-marco-MiniLM-L6-v2`.

## Evaluation notes (flywheel)

- Failure modes observed: mxbai-rerank-xsmall loads in float16 on CPU and did not finish in time; the agent-context script made only an encoding change.
- Graders run and results (PASS/FAIL): Constitution Check PASS, with one justified exception.
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
