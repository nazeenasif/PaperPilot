---
id: 4
title: Localhost Binding And Rate Limit Rules
stage: spec
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 003-web-app
branch: 003-web-app
user: Nazeen Asif
command: direct request
labels: ["spec", "security", "localhost", "cors", "rate-limit", "retry-policy"]
links:
  spec: specs/003-web-app/spec.md
  ticket: null
  adr: history/adr/0003-llm-boundary-and-retry-policy.md
  pr: null
files:
 - specs/003-web-app/spec.md
 - specs/003-web-app/checklists/requirements.md
tests:
 - none (specification)
---

## Prompt

Both the API and the frontend dev server bind to 127.0.0.1 only (set explicitly; Next.js listens on all interfaces by default), and the API's CORS allows only the frontend's localhost origin. Network access, authentication and deployment are a later feature. The daily counter resets at the provider's reset time (verify; expected 00:00 UTC), includes retries, and is replaced by the provider's own remaining-requests figure whenever a response reports it. Concurrent writers (app and scripts) must not lose counts.When the provider's requested wait exceeds the retry cap (60 s), the engine stops retrying at once and raises a readable "rate limited until <time>" error; the UI shows the daily-limit screen if the daily quota is exhausted, otherwise "try again at <local time>". Implemented in llm.py with fake-client tests. X-RateLimit-Reset is accepted only if it resolves to a time in the future within 48 hours; otherwise it is ignored and normal backoff applies. Confirm its units from the first real 429.

## Response snapshot

Recorded as a refinement bullet in Clarifications. FR-002a: both servers bind explicitly to
127.0.0.1; API CORS only the frontend's localhost origin. FR-023a: stop at once, readable "rate
limited until <time>" error; daily-limit screen if quota exhausted, else "try again at <local
time>". New FR-023b (X-RateLimit-Reset trusted only if future and within 48 h, else backoff;
units confirmed from the first real 429) and FR-023c (in the engine's LLM module with fake-client
tests: long wait, at cap, past, beyond 48 h, wrong units). Out of Scope: network access,
authentication, accounts, sharing, deployment are a later feature. Assumptions: two provider
facts to verify. New SC-012 (localhost binding, CORS) and SC-013 (long wait spends one request).
FR-025 already held the counter rules; unchanged. Checklist notes the deliberate technical
detail. No code changed in this step.

## Outcome

- ✅ Impact: security and retry rules precise enough to test before planning.
- 🧪 Tests: none (llm.py tests are planned work, FR-023c).
- 📁 Files: spec.md, checklists/requirements.md
- 🔁 Next prompts: /sp.plan.
- 🧠 Reflection: the 48-hour window also makes a wrong unit for X-RateLimit-Reset fail safe (a seconds value read as milliseconds lands in 1970 and is ignored).

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): checklist PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
