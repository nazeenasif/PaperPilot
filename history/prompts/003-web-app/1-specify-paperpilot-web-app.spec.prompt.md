---
id: 1
title: Specify PaperPilot Web App
stage: spec
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 003-web-app
branch: 003-web-app
user: Nazeen Asif
command: /sp.specify
labels: ["spec", "web-app", "fastapi", "nextjs", "source-viewer", "failure-states"]
links:
  spec: specs/003-web-app/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/003-web-app/spec.md
 - specs/003-web-app/checklists/requirements.md
tests:
 - none (specification)
---

## Prompt

/sp.specify Feature 3: PaperPilot web app — FastAPI backend + Next.js frontend for the library and question answering. Visual reference: docs/design/ask.png, library.png, states.png (dark cinematic: ink background #07090D, panels #10141B, teal #5EEAD4 for verified/grounded, amber #F5B454 for citations and highlights; Sora headings, Inter body, JetBrains Mono for system details).

User stories:
1. As a researcher, I drag and drop PDFs and watch each one move through Parsing → Chunking → Embedding → Ready, then appear as a card with its passage, section and page counts. Duplicates are recognised.
2. As a researcher, I ask a question and get the answer with numbered citation chips and an "all citations verified" badge.
3. As a researcher, I click a citation and the source viewer opens the actual PDF at the cited page with the retrieved passage highlighted.
4. As a researcher, I choose which papers a question searches, and follow-up questions show what they were searched as.
5. As a researcher, every failure looks designed and friendly: not-found with suggestions, a countdown while the free model is busy, the daily-limit screen with remaining requests, an answer held back for an invalid citation (with the unverified text viewable), and uncited sentences gently flagged.

Requirements:
- The Python engine (paperpilot package) stays the single source of logic; FastAPI exposes it; the frontend never calls the LLM.
- The embedding model and library load once at server start; adding a paper runs in the background with progress updates.
- The API returns everything the UI needs from ask(): answer, citations, passages with page numbers, fallback_reason, warnings, the rewritten query, and timings.
- The UI shows today's request usage against the daily free limit.
- Works at phone width; keyboard accessible; text meets 4.5:1 contrast.

Out of scope: summaries, comparison, user accounts, deployment.

## Response snapshot

Branch 003-web-app created (create-new-feature.ps1 hit the known PowerShell 5.1 Join-Path error
after creating the branch and spec; prompts folder made by hand). Studied the three mock-ups.
Spec: stories ordered by priority — Ask with verified citations (P1), Open citation in PDF (P1,
constitution IX), Add papers with progress (P2), Scope and follow-ups (P2), Designed failure
states (P2); 33 FRs, 10 SCs, edge cases, assumptions, dependencies, out of scope. Mock-up
deviations recorded: Summarize/Compare excluded; busy state uses the engine's attempt count (4).
Delete paper kept (design and engine have it). Engine dependencies: stored PDF copies, ingest
progress, retry-wait reporting, persistent daily request count, section and text/table counts,
arXiv id. One clarification raised: stream answer text before citation checks (FR-011).

## Outcome

- ✅ Impact: Feature 3 spec drafted; one question for the researcher.
- 🧪 Tests: none.
- 📁 Files: spec.md, checklists/requirements.md
- 🔁 Next prompts: answer FR-011; then /sp.clarify or /sp.plan.
- 🧠 Reflection: the library stores no PDF today, so "open the PDF at the cited page" is an engine dependency, not only a UI task.

## Evaluation notes (flywheel)

- Failure modes observed: create-new-feature.ps1 Join-Path parameter error (known).
- Graders run and results (PASS/FAIL): checklist all pass except the open marker
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
