---
id: 2
title: Tab icon and compare across pages
stage: general
date: 2026-11-13
surface: agent
model: claude-opus-5-5
feature: none
branch: fix-source-viewer-fit
user: Nazeen Asif
command: none
labels: ["frontend", "favicon", "compare", "state", "bugfix"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - frontend/app/icon.svg
 - frontend/components/compare/ComparisonProvider.tsx
 - frontend/components/compare/CompareView.tsx
 - frontend/app/layout.tsx
 - frontend/tests/setup.ts
 - frontend/tests/compare-session.test.tsx
 - frontend/e2e/smoke.spec.ts
tests:
 - frontend/tests/compare-session.test.tsx (3 new; Vitest 226 passed)
 - frontend/e2e/smoke.spec.ts (tab icon; comparison across a page visit; Playwright 43 passed)
---

## Prompt

1)add a logo in the tab also because there is no logo shown in the tab bar. 2)when i open compare page and compares the papers then navigate to another page and cameback on compare page there was no comparison happening and when i start to comparing again the paper it shows "PaperPilot is still working on another answer, summary or comparison", it should be there while comparing the papers either i navigate to another pages and camback

## Response snapshot

1) app/icon.svg: the header mark (lucide Navigation2 at 45°, teal on ink, teal ring); Next.js links it as the tab icon; e2e checks the link and that it loads. 2) Cause: the Compare screen's selection and running stream lived in the page component, so navigating unmounted them while the server kept working (a new start then got "busy"). Moved papers, aspects and the comparison (useComparison) into a ComparisonProvider in the root layout, kept the choice in sessionStorage across reloads; CompareView brings its own provider outside the layout. Tests first (Vitest), plus an e2e run that leaves for Library mid-comparison and returns to the finished table with one POST (fails without the fix). Committed on fix-source-viewer-fit; not pushed.

## Outcome

- ✅ Impact: tab shows the logo; a comparison keeps running and is shown after visiting other pages.
- 🧪 Tests: Vitest 226 passed; Playwright 43 passed; tsc clean.
- 📁 Files: listed above.
- 🔁 Next prompts: the same for Summarize (useSummary keeps its run in the page); push and PR.
- 🧠 Reflection: a full reload mid-run still loses the live stream; the saved comparison appears once the server finishes.

## Evaluation notes (flywheel)

- Failure modes observed: e2e navigation slow on a cold dev server (warm-up and longer timeouts added).
- Graders run and results (PASS/FAIL): Vitest PASS, Playwright PASS, tsc PASS.
- Prompt variant (if applicable): none.
- Next experiment (smallest change to try): none.
