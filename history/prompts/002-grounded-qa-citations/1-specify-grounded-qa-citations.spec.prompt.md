---
id: 1
title: Specify Grounded QA with Citations
stage: spec
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: /sp.specify
labels: ["spec", "rag", "citations", "grounding", "llm"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/002-grounded-qa-citations/spec.md
 - specs/002-grounded-qa-citations/checklists/requirements.md
tests:
 - none
---

## Prompt

Feature 2: Grounded question answering with citations for PaperPilot (see docs/paperpilot-guide.pdf, Phases 4–5; builds on Feature 1's library and search).

Goal: a researcher asks a question about the papers in their library and gets a concise answer written only from retrieved passages, where every factual claim carries a numbered citation like [2] that maps to a passage with paper title, section and page. When the passages don't contain the answer, the system says exactly "I couldn't find that in the selected papers." instead of guessing.

User stories:
1. As a researcher, I ask a question and get a cited answer plus the list of passages it was based on.
2. As a researcher, I ask something the papers don't cover and get the exact not-found sentence.
3. As a researcher, I limit a question to selected papers.
4. As a researcher, I ask a follow-up ("what about its limitations?") and the system understands what "its" refers to from the conversation.
5. As a researcher, I am warned when the answer cites a passage number that wasn't provided.

Functional requirements:
- Retrieve the top k passages (default 6) using Feature 1's search, honoring the paper filter.
- Drop passages below a configurable relevance threshold before answering; if none remain, return the not-found sentence without calling the LLM. The threshold default must be calibrated with evidence (scores of clearly off-topic questions vs real ones), because bge scores cluster high.
- Send the LLM numbered passages with title, section and page; instructions require citing every claim, never inventing numbers, datasets, authors or citations, copying numbers exactly, and the exact not-found sentence when unsupported.
- Passage text is treated as data, never as instructions (prompt-injection safety).
- Validate citations in code: report which cited numbers are valid and which don't map to a provided passage.
- Follow-up questions are rewritten into a standalone search query using recent conversation history (last 6 turns); the rewritten query is returned so it can be inspected. No history means no rewrite call.
- The LLM provider and model come from settings (LLM_PROVIDER, LLM_MODEL, API key in .env); only one module talks to the LLM, so adding another provider later touches nothing else. Gemini is the only provider in this feature.
- Free-tier rate limits and transient errors are retried with exponential backoff; persistent failure gives a clear, readable error, not a stack trace.
- Each answer reports timings (rewrite, retrieve, generate) and token counts where the provider returns them.

Out of scope: summaries, comparison, UI, API, streaming, other LLM providers, the full evaluation harness, reranking or hybrid search.

Acceptance criteria (guide Checkpoints 4–5):
- A question the papers answer returns a cited answer whose citations all map to provided passages.
- "What is the capital of France?" returns exactly the not-found sentence.
- A filtered question uses only passages from the selected paper(s).
- A follow-up using "it" or "that method" produces a sensible standalone query and a relevant answer.
- The five questions in eval/probe_notes.md are run and recorded; where retrieval missed the answer (Q2, Q4), the correct behaviour is not-found or a partial answer, never an invented one.
- No API key appears in any committed file, log or error message.

## Response snapshot

Created branch 002-grounded-qa-citations (numbered 002 to follow Feature 1; the script's
per-short-name rule would have restarted at 001; script again failed only at its final
Join-Path step). Wrote spec.md: 5 user stories (P1 cited answers, P1 not-found, P2 filter,
P2 follow-ups, P2 citation validation), 8 edge cases, FR-001–FR-019, 5 entities,
SC-001–SC-010, assumptions (caller supplies history, turn = one message, retries 4 × doubling
from 1 s, 60 s call limit), out of scope. One open question: invalid/missing citations →
warn (user story) vs not-found (constitution Principle V). Checklist: all pass except the open
clarification.

## Outcome

- ✅ Impact: Feature 2 spec drafted; one decision needed before planning.
- 🧪 Tests: none (spec stage)
- 📁 Files: spec.md, checklists/requirements.md
- 🔁 Next prompts: answer Q1 (citation failure behaviour), then /sp.clarify or /sp.plan
- 🧠 Reflection: The user story and the constitution disagree; surfaced rather than guessed.

## Evaluation notes (flywheel)

- Failure modes observed: create-new-feature.ps1 Join-Path incompatibility with PowerShell 5.1 (known).
- Graders run and results (PASS/FAIL): spec quality checklist 15/16 (clarification pending)
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
