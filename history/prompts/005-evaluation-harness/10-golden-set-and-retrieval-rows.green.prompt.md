---
id: 10
title: Golden set and retrieval rows
stage: green
date: 2026-11-13
surface: agent
model: claude-opus-5-5
feature: 005-evaluation-harness
branch: 005-evaluation-harness
user: Nazeen Asif
command: none
labels: ["evaluation", "golden-set", "retrieval", "reranking", "hybrid", "report"]
links:
  spec: specs/005-evaluation-harness/spec.md
  ticket: null
  adr: history/adr/0012-retrieval-experiments-and-gate.md
  pr: null
files:
 - eval/golden.json
 - eval/experiments.json
 - eval/results/baseline.json
 - eval/results/rerank-minilm-l6.json
 - eval/results/rerank-tinybert.json
 - eval/results/hybrid-rrf60.json
 - eval/results/prefix.json
 - eval/results.md
 - README.md
 - evaluation/retrieval.py
 - evaluation/libraries.py
 - evaluation/report.py
 - evaluation/golden.py
 - evaluation/__main__.py
 - paperpilot/library.py
 - specs/005-evaluation-harness/tasks.md
tests:
 - tests/evaluation/test_retrieval_metrics.py
 - tests/evaluation/test_retrieval_run.py
 - tests/evaluation/test_rerank.py
 - tests/evaluation/test_hybrid.py
 - tests/evaluation/test_libraries.py
 - tests/evaluation/test_report.py
 - tests/test_embed_prefix.py
 - full pytest: 1053 passed
---

## Prompt

Change of plan: I won't write the questions myself. You draft the 12 golden questions in eval/golden.json: 2 per paper plus 2 near-miss. Include Q2 (BERT's two pre-training tasks) and Q4 (LoRA's rank for GPT-3) from eval/probe_notes.md. Write them in plain wording, not copied from the papers.

For each answerable question, find the evidence phrase and page, check it against the PDF itself, and set confirmed only after that check. Add a note to the golden set and the README: "Questions drafted by Claude Code, reviewed by Nazeen Asif." Make sure the check passes.

Then build and run the five retrieval experiments (baseline, MiniLM reranker, TinyBERT reranker, hybrid, prefix), and draft a one-line takeaway for each row. Show me the 12 questions and the results table, then stop. Don't push yet.

## Response snapshot

Drafted 12 questions (10 single, 2 per paper, Q2 and Q4 included; 2 near-misses checked absent from all 5 PDFs). Each evidence phrase was read in context in the PDF and matched by the check on its page and in a stored passage; confirmed set, version 1; `check` passes. Built T020-T031 and T048-T049 test-first (retrieval metrics, vector, MiniLM/TinyBERT reranking, BM25+RRF hybrid, EMBED_PREFIX and its own library, report). Rows: hit@6 0.4/0.5/0.5/0.6/0.5, MRR 0.311/0.246/0.260/0.315/0.407; 0 model requests; library unchanged. Drafted takeaways (T050), generated eval/results.md and a new README.md (T051). Not pushed.

## Outcome

- ✅ Impact: reduced Checkpoint 11 met: golden set, baseline and four experiments with takeaways, generated table.
- 🧪 Tests: 1053 passed.
- 📁 Files: listed above.
- 🔁 Next prompts: researcher reviews the questions and takeaways; push and PR when approved.
- 🧠 Reflection: rag-02's evidence is never in any top 20; near-misses are never gated (0 of 2), so refusals depend on the model.

## Evaluation notes (flywheel)

- Failure modes observed: no README existed; created a minimal one.
- Graders run and results (PASS/FAIL): pytest PASS; golden check PASS.
- Prompt variant (if applicable): none.
- Next experiment (smallest change to try): hybrid + prefix combined (two changes, so a new baseline).
