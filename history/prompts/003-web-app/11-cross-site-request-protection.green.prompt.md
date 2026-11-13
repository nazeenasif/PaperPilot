---
id: 11
title: Cross Site Request Protection
stage: green
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 003-web-app
branch: 003-web-app
user: Nazeen Asif
command: direct request
labels: ["security", "csrf", "cors", "origin", "x-paperpilot", "agents-md"]
links:
  spec: specs/003-web-app/spec.md
  ticket: null
  adr: history/adr/0005-web-stack-and-progress-transport.md
  pr: null
files:
 - frontend/AGENTS.md
 - specs/003-web-app/{spec.md,tasks.md,research.md,plan.md,quickstart.md,contracts/web-api.md,contracts/engine-api.md}
 - history/adr/0005-web-stack-and-progress-transport.md
 - tests/test_settings.py
 - tests/api/test_app.py
 - tests/api/test_security.py
 - frontend/tests/api-client.test.ts
 - frontend/tests/sse.test.ts
 - api/security.py
 - api/main.py
 - api/errors.py
 - paperpilot/config.py
 - frontend/lib/api.ts
 - frontend/lib/sse.ts
 - .env.example
 - scripts/checkpoint_6_web.py
tests:
 - pytest: 390 passed
 - vitest: 52 passed
 - scripts/checkpoint_6_web.py boundary: PASS, 0 model requests
---

## Prompt

1. Read frontend/AGENTS.md, tell me in two lines what it instructs, then commit it.
2. Add finding A1 to the spec and tasks now, before any write endpoint: the API rejects requests whose Origin header is present and not an allowed frontend origin, and every state-changing endpoint requires the header X-PaperPilot: 1 (forcing a CORS preflight). Tests first: a cross-origin simple POST is refused; a write without the header is refused; the frontend client sends the header. Allow both http://127.0.0.1:3000 and http://localhost:3000 as frontend origins. Record the reasoning in research and the web-stack ADR. Commit.

## Response snapshot

AGENTS.md (written by next dev): tells coding agents this Next.js has breaking changes versus
their training data and to read node_modules/next/dist/docs/ and heed deprecations before
writing code; committed (78e0e04). A1: spec clarification amendment, FR-002a (both origins),
new FR-002b, SC-012; research R11 (why CORS is not enough, the two rules, alternatives); ADR-0005
network boundary, consequences, alternatives H–I; contract forbidden kind and rules;
FRONTEND_ORIGIN → FRONTEND_ORIGINS; tasks T072–T074 (0243127). T072 failing tests (f396af2):
cross-origin simple, multipart, header-bearing and read requests refused (403 forbidden/origin)
before the endpoint runs; writes without the header refused (403 forbidden/header) from allowed
origins and scripts; writes with the header from both origins run; frontend sends the header.
T073 (2e7fa8c): api/security.py OriginGuard between trusted hosts and CORS, CORS allows
X-PaperPilot, forbidden kind, comma-separated FRONTEND_ORIGINS, frontend WRITE_HEADERS. T074
boundary part extended and run live: PASS.

## Outcome

- ✅ Impact: no web page other than PaperPilot's own can change the library or spend requests.
- 🧪 Tests: pytest 390 passed; vitest 52 passed; checkpoint 6 boundary PASS (0 requests).
- 📁 Files: see list.
- 🔁 Next prompts: engine US1/US2 (T019–T026); every later write sends X-PaperPilot: 1.
- 🧠 Reflection: the guard sits before routing, so even non-existent write paths are refused for the right reason — the checkpoint can probe it without creating anything.

## Evaluation notes (flywheel)

- Failure modes observed: none new.
- Graders run and results (PASS/FAIL): pytest PASS; vitest PASS; checkpoint 6 boundary PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
