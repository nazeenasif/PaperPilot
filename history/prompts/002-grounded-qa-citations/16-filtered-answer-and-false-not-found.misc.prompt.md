---
id: 16
title: Filtered Answer and False Not-Found
stage: misc
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: none (direct request)
labels: ["us3", "filter", "ranking", "false-not-found", "reranking"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: history/adr/0004-grounding-and-citation-validation.md
  pr: null
files:
 - scripts/checkpoint_4_answer.py
 - eval/probe_notes.md
 - docs/known-limitations.md
tests:
 - one-off filtered question: PASS, 1 LLM request
 - BERT-filtered search k=60: 0 LLM requests
---

## Prompt

Add the second filtered US3 question (BERT's pre-training data, 1 request) and confirm a cited answer through the filter. Then, with no LLM requests, find the rank of the Masked LM and Next Sentence Prediction passages in a BERT-filtered search with k=60, and record in eval/probe_notes.md: "Filtering to one paper does not fix within-paper ranking; Q2 is a false not-found under the filter." Mark reranking as the top-priority experiment for the evaluation feature, and add this false not-found to docs/known-limitations.md. Commit.

## Response snapshot

Checkpoint 4 US3 now asks two filtered questions: the tasks question (known false not-found,
INFO) and "What data was BERT pre-trained on?" (must give a cited answer). Ran only the new
question via a scratchpad one-off (1 request): "BERT was pre-trained on the BooksCorpus (800M
words) and English Wikipedia (2,500M words) [1]." — passage [1] (BERT, p. 5) states exactly
that; 2.49 s. BERT-filtered k=60 search (0 requests): Masked LM rank 13 (0.762), NSP rank 22
(0.725) vs top 6 at 0.796–0.844; library-wide ranks were 13 and 25. Recorded the finding and
sentence in eval/probe_notes.md, marked cross-encoder reranking as top priority, and added a
"Question answering" section to docs/known-limitations.md.

## Outcome

- ✅ Impact: filtered answering confirmed; false not-found documented with evidence.
- 🧪 Tests: 1 LLM request; search measurement 0 requests.
- 📁 Files: see list.
- 🔁 Next prompts: US4 (T024–T028).
- 🧠 Reflection: the filter narrows the paper set, not the within-paper ranking.

## Evaluation notes (flywheel)

- Failure modes observed: none new.
- Graders run and results (PASS/FAIL): filtered cited answer PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): cross-encoder rerank of the top 20 for Q2 and Q4.
