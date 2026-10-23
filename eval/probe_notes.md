# Retrieval probe — 2026-10-24

A quick check of `library.search(query, k=6)` over the whole library (the 5 test papers,
default settings: CHUNK_WORDS=220, CHUNK_OVERLAP=40, bge-small-en-v1.5). No code changes.
"Answer rank" is the rank of the first passage whose **full text** contains the answer,
checked by searching for the evidence phrase. For answers outside the top 6 the rank comes
from the same query run with k=60.

| # | Query | Expected paper / section | Evidence phrase | Answer rank (k=6) | Notes |
|---|---|---|---|---|---|
| 1 | Which dataset was the Transformer trained on for English-German translation? | Attention / Training | "We trained on the standard WMT 2014 English-German dataset consisting of about 4.5 million sentence pairs" | 2 (partial) | #2 (Results) names "the WMT 2014 English-to-German translation task", which answers the question. The training-data passage (`a639448e61be-20`, Training) ranks 11. #1 is LoRA's Related Work on Transformers. |
| 2 | What are the two pre-training tasks of BERT? | BERT / BERT (3.1 Pre-training BERT) | "Task #1: Masked LM", "Task #2: Next Sentence Prediction (NSP)" | not in top 6 | Masked LM passage (`a7b7a17d0cf9-11`) ranks 13; NSP passage (`a7b7a17d0cf9-14`) ranks 25. The two tasks are in different passages. All top 6 are from BERT but talk about pre-training in general (data, framework, abstract). |
| 3 | How many retrieved documents does RAG use at test time? | RAG / Experiments, Results ("Effect of Retrieving more documents") | "We consider k ∈ {5, 10} for training and set k for test time using dev data"; "Models are trained with either 5 or 10 retrieved latent documents" | 2 | #2 (Experiments) and #3 (Results) both contain the answer. #1 is a figure-axis-heavy passage ("10 20 30 40 50 K Retrieved Docs"). |
| 4 | What rank r does LoRA use for GPT-3? | LoRA / Understanding the Low-Rank Updates (7.1) | "on GPT-3 175B, which corresponds to r = 8 if we adapt one type of attention weights or r = 4 if we adapt two types" | not in top 6 | Answer passage (`a8ca46b17146-41`) ranks 18. Top 6 are all LoRA but about GPT-3 results tables and setup. The "7.2 What is the optimal rank r" passage ranks 7 but does not state a value in its text. |
| 5 | Where in the context do models use information best? | Lost in the Middle / Introduction, Results | "relevant information that occurs at the very beginning (primacy bias) or end of its input context (recency bias)" | 2 | #2, #4 and #6 all contain the answer. |

## Summary

- Answer in the top 6 for 3 of 5 queries (1 only partly). The expected **paper** fills at
  least 5 of the top 6 for every query (Q1's #1 is LoRA's Related Work on Transformers).
- Misses (2, 4) are cases where the answer sits in one specific passage among many
  on-topic passages of the same paper; generic passages about the topic outrank it.
- Scores cluster tightly within a query (e.g. Q2 0.796–0.844), so small embedding
  differences decide the order.

## Baseline

Configuration: library-wide search, k=6, `BAAI/bge-small-en-v1.5`, chunking 220/40.

| Metric | Value |
|---|---|
| hit@6 | 3/5 (one partial: Q1) |
| MRR@6 | ≈ 0.30 (ranks 2, –, 2, –, 2 → (0.5 + 0 + 0.5 + 0 + 0.5) / 5) |

Five queries are too few for conclusions; treat this as a smoke test, not a benchmark.

## Candidate experiments (for the evaluation feature, in this order)

1. Cross-encoder reranking of the top 20 vector results.
2. Hybrid search: BM25 keyword scores combined with vector scores.
3. Paper title and section name prepended to passage text before embedding.

Each should be measured against this baseline on the same queries (extended into the eval
harness), one change at a time.
