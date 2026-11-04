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
| 6 | What is the context window of Claude? | Lost in the Middle / Multi-Document Question Answering, p. 5 | "Claude-1.3 (100K) has an extended context length of 100K tokens" (and "Claude-1.3 has a maximum context length of 8K tokens") | 1 | Added 2026-10-24 after checkpoint 4 showed the papers answer it (first labelled a topic-level near-miss by mistake). The model answered with valid citations [1, 3]. Not part of the 5-query baseline below. |

## Summary

- Answer in the top 6 for 3 of 5 queries (1 only partly). The expected **paper** fills at
  least 5 of the top 6 for every query (Q1's #1 is LoRA's Related Work on Transformers).
- Misses (2, 4) are cases where the answer sits in one specific passage among many
  on-topic passages of the same paper; generic passages about the topic outrank it.
- Scores cluster tightly within a query (e.g. Q2 0.796–0.844), so small embedding
  differences decide the order.

## Filtered search (BERT only)

Same Q2 search restricted to the BERT paper (`paper_ids=["a7b7a17d0cf9"]`, 42 passages),
k=60, no LLM requests:

| Evidence | Rank within BERT | Score | Rank library-wide (above) |
|---|---|---|---|
| "Task #1: Masked LM" (`a7b7a17d0cf9-11`, BERT, p. 4) | 13 | 0.762 | 13 |
| "Task #2: Next Sentence Prediction (NSP)" (`a7b7a17d0cf9-14`, BERT, p. 4) | 22 | 0.725 | 25 |

The top 6 within BERT score 0.796–0.844 and are general passages about BERT (pre-training
data, framework, abstract). Checkpoint 4's US3 part asked Q2 filtered to BERT and the model
correctly replied not-found from those passages.

**Filtering to one paper does not fix within-paper ranking; Q2 is a false not-found under
the filter.** A filtered question whose evidence does rank first ("What data was BERT
pre-trained on?", BooksCorpus passage at rank 1) gets a correct cited answer.

## Baseline

Configuration: library-wide search, k=6, `BAAI/bge-small-en-v1.5`, chunking 220/40.

| Metric | Value |
|---|---|
| hit@6 | 3/5 (one partial: Q1) |
| MRR@6 | ≈ 0.30 (ranks 2, –, 2, –, 2 → (0.5 + 0 + 0.5 + 0 + 0.5) / 5) |

Five queries are too few for conclusions; treat this as a smoke test, not a benchmark.

## Candidate experiments (for the evaluation feature, in this order)

1. **Top priority:** cross-encoder reranking of the top 20 vector results. The Q2 and Q4
   misses, and the Q2 false not-found under a paper filter, are within-paper ranking problems
   that a filter cannot fix; reranking addresses them directly.
2. Hybrid search: BM25 keyword scores combined with vector scores.
3. Paper title and section name prepended to passage text before embedding.

Each should be measured against this baseline on the same queries (extended into the eval
harness), one change at a time.

## Faithfulness cases

Citation validation (ADR-0004) checks only that each [n] points to a provided passage. These
cases passed it but the cited passage does not fully support the claim. They are the
evaluation feature's faithfulness test cases (claim-level support, not citation range).

### F1. Correct fact, wrong passage (checkpoint 5, 2026-10-24)

- **Question**: "How does that method reduce the number of trainable parameters?", rewritten
  to "How does LoRA reduce the number of trainable parameters?" (model
  `nvidia/nemotron-3-ultra-550b-a55b:free`, threshold 0.59, filter semantics).
- **Sentence**: "The authors further limit adaptation to attention weights (e.g., Wq and Wv)
  while freezing MLP modules for parameter efficiency [2]."
- **Passage [2]** (LoRA, Our Method p. 5, §4.2) supports "attention weights" and "freeze the
  MLP modules … for simplicity and parameter-efficiency", but lists all four attention
  matrices (Wq, Wk, Wv, Wo) and never singles out Wq and Wv.
- **Where the fact is**: passage [1] (Empirical Experiments p. 6), also provided: "we only
  apply LoRA to Wq and Wv in most experiments for simplicity". The fact is correct and
  grounded, but attributed to the wrong passage; [1, 2] would have been faithful.
- **Validation result**: citations valid [1, 2, 5, 6], invalid [] → passed, no warning.

### F2. Overgeneralisation when combining passages (threshold-gate rerun, 2026-10-24)

- **Question**: "What is LoRA?" (threshold 0.58, top-score gate, all 6 passages sent).
- **Sentence**: "LoRA matches or exceeds full fine-tuning performance on NLU and NLG tasks with
  comparable or fewer trainable parameters [2, 4, 6]."
- **Passages**: [4] says "matches or exceeds the fine-tuning baseline" for GPT-3 175B only;
  [2] calls LoRA "a competitive alternative to full fine-tuning on NLU"; [6] (Table 3) says
  LoRA "outperforms several baselines with comparable or fewer trainable parameters" on
  NLG. The sentence applies [4]'s strongest wording to all three.
- **Validation result**: citations valid [2, 3, 4, 6], invalid [] → passed, no warning.

**Further occurrences of F2.** All three came from combining sources, and each passed validation.

- **Second (checkpoint 6, part `ask`, 2026-10-25)**: "What is LoRA?" again, a later run with the same
  shape: "LoRA matches or exceeds full fine-tuning performance on various benchmarks including GLUE,
  E2E NLG Challenge, and GPT-3 175B tasks, while using far fewer trainable parameters [2, 4, 6]."
  Citations valid [2, 3, 4, 6], verified. This run's passages were not saved; the sentence comes from
  the run's output, and the case was identified on 2026-11-04.
- **Third (checkpoint 7, LoRA summary, 2026-11-04)**: TL;DR claim 2: "Experiments on RoBERTa,
  DeBERTa, GPT-2, and GPT-3 across GLUE, WikiSQL, and SAMSum show LoRA matches or beats fine-tuning,
  though merging weights limits multi-task batching unless modules are selected dynamically [9, 13,
  14, 12, 15]."
  - The Results section it was built from had scoped the claim correctly: "LoRA matches or exceeds
    fine‑tuning on GPT‑3 175B across three datasets [13]." The scope was lost when the TL;DR combined
    Data, Results and Limitations, so this one arose from combining verified sections, not passages.
  - The TL;DR check passed: every sentence cites, every citation belongs to a verified section, and
    the sentence states only the numbers in its model names. It cannot see a broadened claim, the same
    blind spot as F1 (research R3 of Feature 4). See `docs/verification/checkpoint-7-2026-11-04.md`,
    claims 2 and 10.
