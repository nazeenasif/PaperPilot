---
id: 1
title: Fit PDF page in source panel
stage: general
date: 2026-11-13
surface: agent
model: claude-opus-5-5
feature: none
branch: fix-source-viewer-fit
user: Nazeen Asif
command: none
labels: ["frontend", "source-viewer", "layout", "bugfix"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - frontend/components/source/SourceViewer.tsx
 - frontend/tests/source-viewer.test.tsx
 - frontend/e2e/smoke.spec.ts
tests:
 - frontend/tests/source-viewer.test.tsx (2 new; Vitest 223 passed)
 - frontend/e2e/smoke.spec.ts US2 viewer (page within the panel; Playwright 39 passed)
---

## Prompt

when i click a citation inside an answer it opens with a highlighted pdf but pdf doesn't fit that side deck it sides are hidden make it look viible

## Response snapshot

Cause: the sheet's `data-[side=right]:w-3/4` and `data-[side=right]:sm:max-w-sm` beat SourceViewer's plain `w-full sm:max-w-xl`, so the panel stayed 384 px while the page was drawn 520 px wide, centred in an overflow-hidden box: both sides clipped (reproduced in Playwright: page 67 px left of the panel on desktop, 26 px on phone). Fix on branch fix-source-viewer-fit (from main): override with the same data-[side=right] variants, and draw the page at the panel's measured content width (ResizeObserver, at most 520 px), so page and highlight scale together. Tests first; screenshots checked on desktop and phone. Not pushed.

## Outcome

- ✅ Impact: the whole cited page is visible in the panel at any width.
- 🧪 Tests: Vitest 223 passed; Playwright 39 passed.
- 📁 Files: listed above.
- 🔁 Next prompts: push the branch and open a PR, or merge into 005.
- 🧠 Reflection: variant-prefixed shadcn classes need same-variant overrides for tailwind-merge to replace them.

## Evaluation notes (flywheel)

- Failure modes observed: one timing flake in the keyboard-only e2e test under load; passes on rerun with and without the fix.
- Graders run and results (PASS/FAIL): Vitest PASS, tsc PASS, Playwright PASS.
- Prompt variant (if applicable): none.
- Next experiment (smallest change to try): none.
