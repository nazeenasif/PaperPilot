---
id: 3
title: Ask screen welcome
stage: general
date: 2026-11-13
surface: agent
model: claude-opus-5-5
feature: none
branch: fix-source-viewer-fit
user: Nazeen Asif
command: none
labels: ["frontend", "ask", "empty-state", "ux"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - frontend/components/ask/AskWelcome.tsx
 - frontend/components/ask/AskScreen.tsx
 - frontend/components/ask/Composer.tsx
 - frontend/tests/ask-welcome.test.tsx
tests:
 - frontend/tests/ask-welcome.test.tsx (7 new; Vitest 233 passed)
 - Playwright 43 passed
---

## Prompt

on the ask page there is nothing instead of plain screen, add something to make it attractive and engaging

## Response snapshot

Added AskWelcome, shown before the first question: eyebrow and heading "Ask your papers anything" with a soft teal glow, a line saying answers come only from the N selected papers with citations, up to four starter questions built from the selected papers' short titles (different kinds per paper plus one comparing two), a three-step "how it works" row (compact on phones), and a Library link when the library is empty. Clicking a suggestion fills and focuses the composer without sending (0 requests until Enter). Tests first; screenshots checked at desktop and phone. Committed on fix-source-viewer-fit; not pushed.

## Outcome

- ✅ Impact: the empty Ask screen explains itself and offers one-click starting questions.
- 🧪 Tests: Vitest 233 passed; Playwright 43 passed; tsc clean.
- 📁 Files: listed above.
- 🔁 Next prompts: push the UI-fixes branch and open a PR.
- 🧠 Reflection: suggestions are templates from titles, not generated, so they cost nothing and never invent content.

## Evaluation notes (flywheel)

- Failure modes observed: none.
- Graders run and results (PASS/FAIL): Vitest PASS, Playwright PASS, tsc PASS.
- Prompt variant (if applicable): none.
- Next experiment (smallest change to try): none.
