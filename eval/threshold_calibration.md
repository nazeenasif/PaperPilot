# Relevance threshold calibration

Date: 2026-10-24. Library: 5 papers in `data\library`. Embedding model: `BAAI/bge-small-en-v1.5`. Chunking: 220/40.

Calibrated **for bge-small-en-v1.5 on this library**; recalibrate when the embedding model, chunking or papers change. Score = top-1 similarity (0–1).

| Group | Question | Top score | Rejected at 0.58 | Rejected at 0.58 |
|---|---|---|---|---|
| on-topic | Which dataset was the Transformer trained on for English-German translation? | 0.782 | no | no |
| on-topic | What are the two pre-training tasks of BERT? | 0.844 | no | no |
| on-topic | How many retrieved documents does RAG use at test time? | 0.738 | no | no |
| on-topic | What rank r does LoRA use for GPT-3? | 0.759 | no | no |
| on-topic | Where in the context do models use information best? | 0.758 | no | no |
| on-topic | what dataset was used for evaluation? | 0.635 | no | no |
| on-topic | What are the limitations? | 0.629 | no | no |
| on-topic | What is LoRA? | 0.618 | no | no |
| on-topic | What is the context window of Claude? | 0.639 | no | no |
| clear off-topic | What is the capital of France? | 0.468 | yes | yes |
| clear off-topic | How do I bake a chocolate cake? | 0.481 | yes | yes |
| clear off-topic | Who won the 2018 FIFA World Cup? | 0.530 | yes | yes |
| clear off-topic | How do I change a flat tire on a car? | 0.489 | yes | yes |
| clear off-topic | What is the boiling point of water at sea level? | 0.544 | yes | yes |
| clear off-topic | Recommend a good movie for tonight | 0.449 | yes | yes |
| word-level near-miss | How do electrical transformers step down voltage? | 0.588 | no | no |
| word-level near-miss | Who invented the BERT muppet character? | 0.513 | yes | yes |
| word-level near-miss | What is the attention span of a goldfish? | 0.558 | yes | yes |
| topic-level near-miss | How was GPT-4 trained? | 0.698 | no | no |
| topic-level near-miss | What is the context window of Claude 3? | 0.662 | no | no |
| topic-level near-miss | How does Llama 2 handle safety tuning? | 0.668 | no | no |

| Group | Questions | Min top | Max top | Rejected at configured | Rejected at suggested |
|---|---|---|---|---|---|
| on-topic | 9 | 0.618 | 0.844 | 0/9 | 0/9 |
| clear off-topic | 6 | 0.449 | 0.544 | 6/6 | 6/6 |
| word-level near-miss | 3 | 0.513 | 0.588 | 2/3 | 2/3 |
| topic-level near-miss | 3 | 0.662 | 0.698 | 0/3 | 0/3 |

- Lowest on-topic top score: **0.618**; suggested threshold = that − 0.03 rounded down = **0.58** (configured: 0.58).
- Margin below the lowest on-topic question: 0.038.
- Margin above the highest clear off-topic question: +0.036 (max 0.544).
- Margin above the highest word-level near-miss question: -0.008 (max 0.588).
- Margin above the highest topic-level near-miss question: -0.118 (max 0.698).
- On-topic questions are never rejected (clarification Q2). Topic-level near-misses are expected to pass the threshold; the model's not-found rule and citation checks are the second line of defence.
