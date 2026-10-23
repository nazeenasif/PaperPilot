---
id: 17
title: Retrieval Probe Five Queries
stage: misc
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 001-pdf-ingest-search
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: none (direct request)
labels: ["retrieval", "probe", "evaluation"]
links:
  spec: specs/001-pdf-ingest-search/spec.md
  ticket: null
  adr: history/adr/0001-local-retrieval-stack.md
  pr: null
files:
 - eval/probe_notes.md
tests:
 - manual retrieval probe (5 queries, k=6; answer ranks re-checked with k=60)
---

## Prompt

Before US2, run a quick retrieval probe (no code changes, don't commit anything except a notes file). For each query below, search the whole library with k=6 and print rank, score, paper title, section and the first 150 characters:

1. "Which dataset was the Transformer trained on for English-German translation?"  (expect WMT 2014, Attention)
2. "What are the two pre-training tasks of BERT?"  (expect masked LM and next sentence prediction, BERT)
3. "How many retrieved documents does RAG use at test time?"  (expect RAG, Results/Effect of retrieving more documents)
4. "What rank r does LoRA use for GPT-3?"  (expect LoRA, could be a table passage)
5. "Where in the context do models use information best?"  (expect beginning and end, Lost in the Middle)

For each, tell me the rank of the first passage that actually contains the answer (or "not in top 6"). Save the queries, expected evidence phrases and observed ranks to eval/probe_notes.md.

## Response snapshot

Ran the probe with a scratchpad script (no repo code changes). Judged answers by searching
each hit's full text for evidence phrases; looked up misses with k=60. Answer ranks: Q1 2
(partial: names the WMT 2014 En–De task; training-data passage ranks 11), Q2 not in top 6
(Masked LM 13, NSP 25), Q3 2, Q4 not in top 6 (r=8/r=4 passage ranks 18), Q5 2. Expected
paper fills ≥5 of top 6 for all queries. Saved eval/probe_notes.md with table, summary and
untested ideas (context headers in embeddings, larger k / reranking, keep as eval baseline).
Committed only the notes file (990b864).

## Outcome

- ✅ Impact: Baseline retrieval quality measured on 5 targeted questions.
- 🧪 Tests: manual probe only.
- 📁 Files: eval/probe_notes.md
- 🔁 Next prompts: US2 (T032–T034); consider the context-header idea during evaluation work.
- 🧠 Reflection: Paper-level retrieval is strong; passage-level precision within a paper is the weak spot.

## Evaluation notes (flywheel)

- Failure modes observed: generic on-topic passages outrank the specific answer passage; answers split across passages (BERT tasks).
- Graders run and results (PASS/FAIL): 3/5 answers in top 6
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): prepend "title — section" to passage text before embedding and rerun the probe.
