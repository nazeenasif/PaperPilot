---
id: 10
title: Implement Setup And Foundational
stage: green
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 003-web-app
branch: 003-web-app
user: Nazeen Asif
command: /sp.implement
labels: ["setup", "foundational", "fastapi", "nextjs", "shadcn", "security", "contrast", "checkpoint-6"]
links:
  spec: specs/003-web-app/spec.md
  ticket: null
  adr: history/adr/0005-web-stack-and-progress-transport.md
  pr: null
files:
 - requirements.txt
 - .gitignore
 - .env.example
 - frontend/package.json
 - frontend/package-lock.json
 - frontend/tsconfig.json
 - frontend/next.config.ts
 - frontend/postcss.config.mjs
 - frontend/app/globals.css
 - frontend/app/layout.tsx
 - frontend/app/page.tsx
 - frontend/components.json
 - frontend/lib/utils.ts
 - frontend/components/ui/{button,checkbox,dialog,sheet,tooltip,progress}.tsx
 - frontend/vitest.config.ts
 - frontend/playwright.config.ts
 - frontend/tests/{setup.ts,smoke.test.ts,api-client.test.ts,sse.test.ts,contrast.test.ts,app-shell.test.tsx}
 - frontend/scripts/copy-pdf-worker.mjs
 - frontend/lib/{types.ts,api.ts,sse.ts}
 - frontend/components/app/{StatusGate.tsx,Header.tsx}
 - frontend/components/states/{GettingReady.tsx,Unreachable.tsx}
 - paperpilot/config.py
 - paperpilot/errors.py
 - api/{__init__.py,__main__.py,main.py,state.py,errors.py,schemas.py,routes.py}
 - tests/test_settings.py
 - tests/test_errors.py
 - tests/api/conftest.py
 - tests/api/test_app.py
 - scripts/checkpoint_6_web.py
 - specs/003-web-app/{tasks.md,research.md,plan.md,contracts/web-api.md}
 - history/adr/0005-web-stack-and-progress-transport.md
tests:
 - pytest: 372 passed
 - vitest: 51 passed (api-client 8, app-shell 7, contrast 23, smoke 2, sse 11)
 - npm audit: 0 vulnerabilities; Python pins clean on OSV
 - scripts/checkpoint_6_web.py boundary: PASS, 0 model requests
---

## Prompt

T001–T018 (Setup and Foundational). Tests first where they apply, one commit per task. Stop after T018 and show: the pytest summary, the Vitest summary (including the contrast test), and the exact commands for me to start the API and the frontend myself.

## Response snapshot

T001–T018 done, one commit per task (plus a security pin commit and a lockfile follow-up).
Security: `next build` printed an upgrade nudge; `npm audit` confirmed critical advisories
GHSA-2464-fhr4-w9xw, GHSA-673q-mjm6-r5xr (RCE) and GHSA-p3m5-59mp-jv5r (DoS) in Next 16.0.0–16.4.0,
first patched in 16.4.1 — pinned 16.4.1 (10 days old; research R1 now says advisories override
the 14-day rule); audit 0, Python pins clean on OSV. shadcn CLI: npx failed with ECOMPROMISED
(cache lock), worked with a clean scratch cache; init replaced fonts with Geist, added a light
:root and a --color-muted clash, and added `cn` and the `shadcn` CLI as runtime deps — reverted:
shadcn variables mapped onto the palette (dark only), classic cn over clsx+tailwind-merge, five
data-* variants copied into globals.css; radix-ui 1.7.0, cva 0.7.1, tw-animate-css 1.4.0 pinned.
Engine: DAILY_REQUEST_LIMIT, FRONTEND_ORIGIN; LLMError.reason (validated), DailyLimitError,
RateLimitedError, PdfMissingError. API: create_app with background loader, readiness guard on
/api/* except status, CORS for FRONTEND_ORIGIN only, trusted hosts, error kinds (not_found and
invalid_request added to the contract), api.log with the key scrubbed, python -m api on
127.0.0.1:8000. Frontend: typed client (ApiError kinds, unreachable), fetch-based SSE reader,
StatusProvider/StatusGate/Header, GettingReady/Unreachable states, contrast test over 21 pairs
(verified it fails with #6B7280). Checkpoint 6 boundary: PASS against both servers (LAN address
192.168.0.38 refused on 8000 and 3000). Cold API start took ~3 min while Next compiled (25 s
alone); checkpoint waits up to 300 s. `next dev` creates frontend/AGENTS.md (left uncommitted).

## Outcome

- ✅ Impact: Setup and Foundational complete; boundary verified live.
- 🧪 Tests: pytest 372 passed; vitest 51 passed; checkpoint 6 boundary PASS (0 requests).
- 📁 Files: see list.
- 🔁 Next prompts: decide on frontend/AGENTS.md (commit or ignore); resolve analysis A1 (Origin check for POST/DELETE) before the first write endpoints (T035, T041); then engine US1/US2 (T019–T026).
- 🧠 Reflection: the "≥ 14 days old" rule chose a release with a critical RCE advisory; an audit must accompany every pin.

## Evaluation notes (flywheel)

- Failure modes observed: npm ECOMPROMISED cache lock; shadcn init overwrote theme and fonts and added unpinned runtime deps; vitest env stubs leaked between tests (fixed with unstubAllEnvs); first Vitest run timed out cold; a loader thread outlived the default 120 s checkpoint wait on a cold start.
- Graders run and results (PASS/FAIL): pytest PASS; vitest PASS; npm audit PASS; checkpoint 6 boundary PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): add an Origin check middleware for state-changing requests (analysis A1).
