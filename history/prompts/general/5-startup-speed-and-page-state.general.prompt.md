---
id: 5
title: Startup speed and page state
stage: general
date: 2026-11-14
surface: agent
model: claude-opus-5-5
feature: none
branch: keep-page-state
user: Nazeen Asif
command: none
labels: ["performance", "startup", "frontend", "state", "navigation"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - frontend/components/ask/AskProvider.tsx
 - frontend/components/ask/AskScreen.tsx
 - frontend/components/ask/Composer.tsx
 - frontend/lib/useSummary.ts
 - frontend/components/summary/SummaryProvider.tsx
 - frontend/app/layout.tsx
 - frontend/tests/page-sessions.test.tsx
 - frontend/e2e/smoke.spec.ts
tests:
 - frontend/tests/page-sessions.test.tsx (4 new; Vitest 237 passed)
 - frontend/e2e/smoke.spec.ts (Ask, summary and upload across a page visit; Playwright 49 passed)
 - pytest through the moved venv: 1059 passed (8 min 24 s, was 9 min 53 s)
---

## Prompt

paperpilot takes a lot of time in starting

(during the work) make sure that all the other pages also isn't losing there state while navigating from another pages

(answer to the startup options) Move .venv to the SSD (Recommended)

## Response snapshot

Startup: measured, not guessed. D: is a 5,400 rpm laptop HDD holding the 1.2 GB .venv (C: is an SSD). Today's API started 8 minutes after boot and spent about 6.5 minutes importing before a 6 s model load; with a warm cache api.main imports in 25 s (openai 8 s, pymupdf 7 s, fastapi 5 s, chromadb 3 s) and torch + sentence-transformers take 25-40 s. With the user's choice, stopped the running API, copied .venv to C:\Users\Naz\.venvs\PaperPilot (35,799 files, 1,175 MB, verified), kept the original as .venv.old and put a junction at D:\Naz\Projects\PaperPilot\.venv. Steady state: about 10 s + 30 s through the SSD against 20 s + 136 s from the HDD copy in the same session.

Page state: Ask kept its conversation and summaries their runs inside the pages, so both were lost on navigation (Compare was fixed earlier; Library already restores from the server's jobs). Added AskProvider (conversation and unsent question) and a per-paper SummaryStore kept by SummaryProvider, both in the root layout. Tests first; e2e for Ask, summary and upload fail without the fix and pass with it. Committed on keep-page-state; not pushed.

## Outcome

- ✅ Impact: Ask, Summarize, Compare and Library keep their state across navigation; Python imports come from the SSD.
- 🧪 Tests: Vitest 237, Playwright 49 passed; pytest run through the junction.
- 📁 Files: listed above (the venv move is outside the repository).
- 🔁 Next prompts: delete .venv.old once satisfied; optionally lazy imports, production web build or a Defender exclusion.
- 🧠 Reflection: the slow start was the disk and file scanning, not the model load (2-6 s).

## Evaluation notes (flywheel)

- Failure modes observed: two heredocs rejected by the shell's quoting; files written with the Write tool instead.
- Graders run and results (PASS/FAIL): Vitest PASS, Playwright PASS, tsc PASS.
- Prompt variant (if applicable): none.
- Next experiment (smallest change to try): time a start after the next reboot.
