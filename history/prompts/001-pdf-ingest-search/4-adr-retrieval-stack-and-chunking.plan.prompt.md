---
id: 4
title: ADR Retrieval Stack and Chunking
stage: plan
date: 2026-10-23
surface: agent
model: claude-opus-5-5
feature: 001-pdf-ingest-search
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: /sp.adr
labels: ["adr", "architecture", "retrieval", "chunking"]
links:
  spec: specs/001-pdf-ingest-search/spec.md
  ticket: null
  adr: history/adr/0001-local-retrieval-stack.md, history/adr/0002-passage-identity-and-chunking.md
  pr: null
files:
 - history/adr/0001-local-retrieval-stack.md
 - history/adr/0002-passage-identity-and-chunking.md
tests:
 - none
---

## Prompt

/sp.adr (no additional input)

## Response snapshot

Reviewed plan.md, research.md, data-model.md and contracts. No existing ADRs. Created two
clustered ADRs (agent-native; no create-adr script exists): ADR-0001 Local Retrieval Stack
(PyMuPDF + column-aware order, bge-small with query-only prefix, single cosine Chroma
collection, score clamp, upsert-then-cleanup) and ADR-0002 Passage Identity and Chunking
Strategy (SHA-1 paper ID, positional passage IDs, sectioning rules, paragraph packing,
metadata schema). Each lists 4 alternatives with pros/cons. Not ADR-worthy: settings
dataclass, logging, atomic add as a standalone (folded into ADR-0001), module layout
(handled by constitution v1.1.0).

## Outcome

- ✅ Impact: Two long-lived architecture contracts recorded before implementation.
- 🧪 Tests: none
- 📁 Files: history/adr/0001-local-retrieval-stack.md, history/adr/0002-passage-identity-and-chunking.md
- 🔁 Next prompts: install Python 3.12; /sp.tasks
- 🧠 Reflection: ADR-0002 surfaced that passage IDs change when chunk settings change, which matters for the future eval harness.

## Evaluation notes (flywheel)

- Failure modes observed: create-adr.sh not present; used agent-native creation.
- Graders run and results (PASS/FAIL): clustered PASS; alternatives listed PASS; pros/cons PASS; concise PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
