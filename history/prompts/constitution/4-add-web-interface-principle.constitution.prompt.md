---
id: 4
title: Add Web Interface Principle
stage: constitution
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: none
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: /sp.constitution
labels: ["constitution", "amendment", "frontend", "nextjs", "fastapi", "principle-ix"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - .specify/memory/constitution.md
tests:
 - none (governance change; no code touched)
---

## Prompt

Amend (MINOR): PaperPilot has a modern web frontend, not a terminal or Streamlit interface. Frontend: Next.js (App Router, TypeScript, Tailwind CSS, shadcn/ui, Framer Motion), in a frontend/ folder. Backend: FastAPI exposing the paperpilot package; the Python engine stays the single source of logic and the frontend never calls the LLM directly. UI principles: grounding is visible (citations open the source PDF at the cited page), long operations show progress, and every failure state (not-found, rate limit, timeout) has a designed, friendly presentation. Streamlit is dropped from the roadmap.

## Response snapshot

Constitution 1.2.0 → 1.3.0 (MINOR). I renamed to "Plain, Typed Code": Python 3.12 for engine and
backend, strict TypeScript for the frontend, no AI/LLM SDKs in the frontend. II adds the FastAPI
backend as a thin adapter (no retrieval/prompt/citation/LLM logic) and frontend-only-via-API.
New IX "Visible Grounding in a Web Interface": Next.js in frontend/, clickable citations open
the PDF at the cited page with title/section/page, progress for long operations, designed
failure states (not-found, rate limit with retry time, timeout, invalid input, unexpected
error), no stack traces/provider bodies/keys in the browser, exact NOT_FOUND shown, no
NEXT_PUBLIC secrets. Stack lists Frontend/Backend; Excluded adds Streamlit/terminal UIs and
frontend LLM calls; quality gates check I–IX and UI failure states in checkpoints. Templates
needed no change. Follow-ups: library does not keep PDFs (needed for citation → page);
web-stack ADR during that feature's plan.

## Outcome

- ✅ Impact: interface direction fixed in governance; Streamlit dropped.
- 🧪 Tests: none (no code change).
- 📁 Files: .specify/memory/constitution.md
- 🔁 Next prompts: finish Feature 2 (US5, polish); then /sp.specify the API + web feature.
- 🧠 Reflection: "open the PDF at the cited page" is a data requirement on Feature 1's library, not only a UI rule.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): placeholder scan PASS; trailing whitespace PASS; version/date lines PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
