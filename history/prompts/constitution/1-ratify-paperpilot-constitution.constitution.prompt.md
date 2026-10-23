---
id: 1
title: Ratify PaperPilot Constitution
stage: constitution
date: 2026-10-23
surface: agent
model: claude-opus-5-5
feature: none
branch: master
user: Nazeen Asif
command: /sp.constitution
labels: ["constitution", "rag", "principles", "governance"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - .specify/memory/constitution.md
 - .specify/templates/tasks-template.md
tests:
 - none
---

## Prompt

PaperPilot is an AI research-paper assistant built with RAG, following docs/paperpilot-guide.pdf.
Principles:
- Python 3.12, plain Python with no LangChain; type hints and short docstrings on public functions.
- Modular package: config, ingest, store, prompts, llm, service. Only llm.py talks to the LLM.
- LLM: free tier (Gemini or Groq), selected via LLM_PROVIDER and LLM_MODEL env vars; swappable without touching other modules.
- Embeddings run locally (BAAI/bge-small-en-v1.5); vector store is persistent ChromaDB.
- Every answer is grounded: numbered citations, citation validation, and an exact "not found" fallback. Never invent facts.
- Secrets only via .env (gitignored); no PDFs or keys committed.
- Every feature ends with a testable checkpoint; pure logic has pytest tests; quality is measured with an eval harness.
- Small, meaningful commits. Prefer simple, explainable solutions over clever ones.

## Response snapshot

Filled the constitution template as v1.0.0 (ratified 2026-10-23) with eight principles: Plain
Typed Python; Modular Package with a Single LLM Boundary; Swappable Free-Tier LLM Provider;
Local Embeddings, Persistent Vector Store; Grounded Answers Only (NON-NEGOTIABLE); Secrets and
Data Hygiene; Testable Checkpoints and Measured Quality; Simplicity and Small Commits. Added
Technology Stack and Constraints, Development Workflow and Quality Gates, and Governance
sections plus a Sync Impact Report. Updated tasks-template.md so tests for pure logic are
required rather than optional.

## Outcome

- ✅ Impact: Project constitution v1.0.0 established; tasks template aligned.
- 🧪 Tests: none (documentation change)
- 📁 Files: .specify/memory/constitution.md, .specify/templates/tasks-template.md
- 🔁 Next prompts: /sp.specify for the first feature (e.g. ingest + store); create .gitignore and .env.example
- 🧠 Reflection: docs/paperpilot-guide.pdf and .gitignore are absent; exact "not found" text deferred to the guide.

## Evaluation notes (flywheel)

- Failure modes observed: create-phr.sh script missing; used agent-native fallback.
- Graders run and results (PASS/FAIL): placeholder scan PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
