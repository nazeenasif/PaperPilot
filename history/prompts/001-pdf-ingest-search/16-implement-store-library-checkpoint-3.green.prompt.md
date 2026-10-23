---
id: 16
title: Implement Store Library and Checkpoint 3
stage: green
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 001-pdf-ingest-search
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: /sp.implement
labels: ["store", "library", "embeddings", "chromadb", "checkpoint-3"]
links:
  spec: specs/001-pdf-ingest-search/spec.md
  ticket: null
  adr: history/adr/0001-local-retrieval-stack.md
  pr: null
files:
 - docs/known-limitations.md
 - paperpilot/store.py
 - paperpilot/library.py
 - scripts/checkpoint_3_search.py
 - specs/001-pdf-ingest-search/tasks.md
tests:
 - pytest (full suite): 171 passed
 - scripts/checkpoint_3_search.py papers: PASS (exit 0)
---

## Prompt

Add one line to the "Tables and figures" entry in docs/known-limitations.md: figure axis labels can be classified as table passages; harmless for search but not real tables. Commit it with the prompt history record.

Then /sp.implement T028–T031: store.py (embedding part, then ChromaDB part), library.py add_paper and search, and checkpoint 3. Make the related tests pass one task at a time, commit after each. Run python scripts\checkpoint_3_search.py papers, show the full output, and stop.

## Response snapshot

f572a50 known-limitations axis-label line (+ PHR 15). T028 7ae7417: lazy SentenceTransformer
(bge-small, CPU), load_model() returning seconds, embed_passages (normalised, batch 32, no
prefix), embed_query (BGE instruction); smoke test dim 384, norm 1, relevant 0.688 vs
unrelated 0.289; first load 42.6 s incl. download. T029 14bb5e4: ChromaDB PersistentClient
per resolved LIBRARY_DIR, cosine collection "passages", reset_cache (also clears chroma's
shared system cache), distance_to_score, build_where, has_paper, upsert_passages (kind and
paper fields in metadata), delete_paper_passages, query → Hit, all_metadata; 8 helper tests
pass. T030 613a9a3: library add_paper (parse→chunk→embed→single upsert; cleanup + StorageError
on write failure; NoTextError if no passages) and search; 13 library tests pass, 171 total.
T031 364de18: checkpoint_3_search.py. Checkpoint 3 PASS: adds 9.8–16.9 s per paper (warm), search
0.053 s, top score 0.635 in band. Relevance by eye: BERT SWAG dataset passages (#2–#4) on
topic; RAG #1 is about human evaluation setup; Lost in the Middle #5–#6 are results
discussion, not datasets.

## Outcome

- ✅ Impact: US1 MVP slice works end to end on the 5 papers.
- 🧪 Tests: 171 passed; checkpoint 3 PASS.
- 📁 Files: store.py, library.py, checkpoint_3_search.py, known-limitations.md, tasks.md.
- 🔁 Next prompts: US2 (T032–T034) duplicate detection; consider SC-004 relevance review.
- 🧠 Reflection: bge-small scores cluster tightly (0.618–0.635 for top 6); ranking among them is noisy.

## Evaluation notes (flywheel)

- Failure modes observed: about half of the top 6 are only loosely about evaluation data.
- Graders run and results (PASS/FAIL): pytest PASS; checkpoint 3 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): compare query phrasing ("evaluation datasets and benchmarks") before changing models.
