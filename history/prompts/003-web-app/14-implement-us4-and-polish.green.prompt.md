---
id: 14
title: Implement US4 and the Polish phase
stage: green
date: 2026-10-25
surface: agent
model: claude-opus-5-5
feature: 003-web-app
branch: 003-web-app
user: Nazeen Asif
command: /sp.implement
labels: ["scope", "follow-ups", "history", "polish", "accessibility", "secrets", "quickstart", "checkpoint"]
links:
  spec: specs/003-web-app/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - tests/api/test_ask_scope.py
 - scripts/checkpoint_6_web.py
 - frontend/lib/useScope.ts
 - frontend/lib/useAsk.ts
 - frontend/components/library/ScopePanel.tsx
 - frontend/components/ask/AskScreen.tsx
 - frontend/components/ask/Conversation.tsx
 - frontend/components/ask/SearchedAs.tsx
 - frontend/components/ask/Composer.tsx
 - frontend/tests/scope.test.tsx
 - frontend/tests/ask.test.tsx
 - frontend/tests/states.test.tsx
 - frontend/e2e/smoke.spec.ts
 - frontend/e2e/fake-backend.ts
 - frontend/e2e/fixtures.ts
 - docs/known-limitations.md
 - specs/003-web-app/quickstart.md
 - specs/003-web-app/tasks.md
tests:
 - tests/api/test_ask_scope.py (T043; mutation-checked)
 - frontend/tests/scope.test.tsx (T060)
 - frontend/e2e/smoke.spec.ts "US4 scope", layout, keyboard only, reveal, reduced motion (T062, T067, T068)
 - scripts/checkpoint_6_web.py scope, secrets and all parts (T045, T069, T071)
 - scripts/checkpoint_6_geometry.py
---

## Prompt

/sp.implement the US4 tasks (paper scope and follow-up searches) in every layer, then the Polish phase (T067–T071). Tests first, one commit per task. Run checkpoint 6's scope part and the full quickstart run, report total model requests, and stop.

## Response snapshot

Implemented T043–T045, T060–T062 and T067–T071, one commit per task, plus one fix commit (c5d4343). All tasks in tasks.md are now [X].

**API (US4):**
- T043's 13 tests passed at once, because scope checks and history validation already existed from T035/T047. A mutation run showed they guard real behaviour: with scope ignored and roles and length unchecked, 5 of the 13 failed.
- T044 is therefore a no-code commit that says so.
- T045 adds checkpoint part `scope` (plan 3). Its follow-up reuses part `ask`'s answer as history, or a fixed summary when `ask` didn't run.

**Frontend (US4):**
- `useScope` handles the selection: ?paper=<id>, else localStorage (inside try/catch), else all papers. The last paper can't be cleared.
- ScopePanel shows as a sidebar on wide screens and as a sheet on phones.
- Conversation and SearchedAs render the turns and "Searched as" notes.
- `useAsk` sends paper_ids only for a subset, and history only from answered, found turns. Leaving out not-found turns means "Search all papers" costs no rewrite request.
- The Composer is blocked when the library is empty.
- The US4 phone test found duplicate label ids (the panel is on the page twice), which left the sheet's checkboxes unnamed. Fixed in c5d4343.

**Polish:**
- T067 adds overflow checks at 375 px and a keyboard-only pass with focus rings.
- T068 adds reveal timing (416–463 ms, budget 500) and a reduced-motion test.
- T069 adds checkpoint part `secrets`. A key planted in `.next/` was detected and removed.
- T070 adds the "Web app" known limitations.
- T071 is the full quickstart run plus the drift fixes, including the `--simulate` flag that doesn't exist.

**Environment events:**
- The servers that were running when the session resumed (PIDs 10884 and 4192, not started by me) stopped during the first scope run. That run had spent 1 request, so I restarted both servers myself and re-ran scope.
- The API log shows the user uploaded "AI Fluency_ the 4Ds Slide Deck.pdf" at 12:10, so the library now has 6 papers and 238 passages. It was left as is.

## Results

| Run | Result | Time |
|---|---|---|
| pytest | 562 passed | 175 s |
| typecheck | clean | 9 s |
| Vitest | 143 passed | 30 s |
| Playwright | 25 passed, 1 skipped (keyboard pass on phone, by design) | 93 s |
| checkpoint 6 `scope` (first try) | interrupted: API went away after question 1 | 1 request |
| checkpoint 6 `scope` | PASS | 3 requests, 0 retries |
| checkpoint 6 all parts | PASS | 4 requests (4 planned, 0 retries; cap 8), 85 s |
| checkpoint 6 geometry | PASS, 223/223 exact | 0 requests, 7 s |

**Model requests this session: 8** (1 + 3 + 4), with 0 retries.
- The provider's counter went from 1/50 to 9/50; the other request is the user's question at 12:11.
- The provider's figure lagged about a minute behind the log: it read 8, then 9.

**Success criteria:**
- **SC-001:** PASS, 4/4 citations open at the cited page.
- **SC-002:** PASS, 4/4 highlighted with 98% word precision; geometry 223/223 exact.
- **SC-003:** PASS. Part `states` covers every kind, with no key, traceback or provider text, and the US5 e2e runs confirm it on screen.
- **SC-004:**
  - PARTIAL: a renamed duplicate is recognised in 0.3 s.
  - The attach path was not exercised, because all PDFs were already stored.
  - The 20-page new-paper run was not done: `--new-pdf` needs papers-extra/1907.11692.pdf, which is not present. The log shows the user's 25-page deck reached Ready in 33 s.
- **SC-005:** PASS, retrieve 0.10 s.
- **SC-006:** PASS, with the note that the provider's figure lags about a minute. The meter equals the provider's figure (9 = 9 replies in the log), and the provider source survives restarts.
- **SC-007:** PASS offline. The pre-check makes 0 generate calls (states part, tests), and Browse passages works (e2e, API test).
- **SC-008:** PASS at 375 px for all stories. The keyboard-only pass runs at desktop width only.
- **SC-009:** PASS (contrast.test.ts).
- **SC-010:** PASS (part `secrets`).
- **SC-011:** PASS: 416–463 ms, reduced motion shows the answer in one step, and no text appears before the check.
- **SC-012:** PASS (part `boundary`).
- **SC-013:** PASS offline (T031 tests, part `states`). No real long wait has been seen.

## Outcome

- ✅ Impact: Feature 3's tasks are all complete. US4 works end to end, and the polish checks are automated.
- 🧪 Tests: see Results.
- 📁 Files: see the list above.
- 🔁 Next prompts:
  - Run `library --new-pdf papers-extra/1907.11692.pdf` once the file is in place, for SC-004.
  - Review and open a PR for 003-web-app.
- 🧠 Reflection: Tests written for behaviour that already exists can't start red. A mutation run is the honest substitute.

## Evaluation notes (flywheel)

- Failure modes observed:
  - Duplicate ids from rendering a panel twice.
  - A file in `.next/dev` locked by a running dev server.
  - Servers stopping mid-run.
  - Vitest worker start timeouts under load.
- Graders run and results (PASS/FAIL): all PASS except SC-004, which is partial (above).
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): run the keyboard-only pass at phone width through the scope sheet.
