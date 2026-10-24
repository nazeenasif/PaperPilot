---
id: 7
title: ADRs Web Stack Geometry Accounting
stage: plan
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 003-web-app
branch: 003-web-app
user: Nazeen Asif
command: /sp.adr
labels: ["adr", "web-stack", "sse", "highlights", "request-accounting", "retry-policy"]
links:
  spec: specs/003-web-app/spec.md
  ticket: null
  adr: history/adr/0005-web-stack-and-progress-transport.md, history/adr/0006-citation-highlight-geometry.md, history/adr/0007-llm-request-accounting-and-long-waits.md
  pr: null
files:
 - history/adr/0005-web-stack-and-progress-transport.md
 - history/adr/0006-citation-highlight-geometry.md
 - history/adr/0007-llm-request-accounting-and-long-waits.md
 - history/adr/0003-llm-boundary-and-retry-policy.md
 - specs/003-web-app/plan.md
tests:
 - none (documentation)
---

## Prompt

/sp.adr web-stack-and-progress-transport
/sp.adr citation-highlight-geometry
/sp.adr llm-request-accounting-and-long-waits

## Response snapshot

No create-adr script exists; ADRs written from .specify/templates/adr-template.md. ADR-0005 Web
Stack and Progress Transport (layout, pinned stack, built-in SSE for ask and jobs with a
snapshot fallback, one ingest worker + threadpool + write lock, background readiness, error
kinds, 127.0.0.1/CORS/trusted hosts, no proxy; alternatives: polling, WebSockets,
sse-starlette, process pool/broker, Next proxy, Streamlit, newest pins). ADR-0006 Citation
Highlight Geometry (word boxes at ingest, hyphen alignment, regions, layout file, attach-time
mapping with id/text check, mismatch marker, read-only get_passage, re-process, viewer overlay;
alternatives: fuzzy matching, block boxes, Chroma JSON, lazy first-view, full re-ingest).
ADR-0007 LLM Request Accounting and Long Waits (SQLite counter in llm.py with BEGIN IMMEDIATE/WAL,
provider free_model_daily_requests preferred, pre-check, no retry beyond 60 s with
RateLimitedError, 48 h reset sanity, raw header logged, on_retry hook; alternatives: headers as
source, local only, usage module, JSON file, keep cap-and-retry, ask the user). ADR-0003 marked
as amended by ADR-0007; plan links the ADRs. All three pass the significance test and the
checklist grader; no conflicts.

## Outcome

- ✅ Impact: three ADRs created, one amended; plan references them.
- 🧪 Tests: none.
- 📁 Files: see list.
- 🔁 Next prompts: /sp.tasks.
- 🧠 Reflection: ADR-0007 records that "provider headers preferred" was impossible as stated; the key endpoint is the real provider source.

## Evaluation notes (flywheel)

- Failure modes observed: no create-adr script (agent-native fallback used).
- Graders run and results (PASS/FAIL): clustered decisions PASS; alternatives listed PASS; pros/cons PASS; concise PASS (each ADR)
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
