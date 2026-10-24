---
id: 3
title: Clarify Access Usage Long Waits
stage: spec
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 003-web-app
branch: 003-web-app
user: Nazeen Asif
command: /sp.clarify
labels: ["clarify", "security", "localhost", "request-usage", "retry-policy"]
links:
  spec: specs/003-web-app/spec.md
  ticket: null
  adr: history/adr/0003-llm-boundary-and-retry-policy.md
  pr: null
files:
 - specs/003-web-app/spec.md
tests:
 - none (specification)
---

## Prompt

/sp.clarify (no arguments). Answers: Q1 "A", Q2 "A", Q3 "A".

## Response snapshot

Three questions asked and answered. Q1 network access → localhost only (FR-002a; FR-029 is a
narrow-window layout requirement; assumption updated). Q2 request counter → every engine request
from any caller (app, scripts) in one shared persistent daily counter (FR-025, SC-006,
assumption). The researcher's own on-disk additions to FR-025 (verify reset time, provider's
remaining-requests figure replaces the estimate, no lost counts with concurrent callers) were
kept and worded as requirements. Q3 provider wait longer than the 60 s cap → no retry, end at
once with the daily-limit state or "try again at <time>" (FR-023a, US5 scenario 3, dependency
noted as an ADR-0003 retry-policy amendment). US5 scenarios renumbered 1–9.

## Outcome

- ✅ Impact: security posture, usage accounting and long-wait behaviour fixed before planning.
- 🧪 Tests: none.
- 📁 Files: specs/003-web-app/spec.md
- 🔁 Next prompts: /sp.plan; amend ADR-0003 for FR-023a during planning.
- 🧠 Reflection: FR-023a also saves free requests in scripts, not only in the app.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): no remaining markers; one bullet per answer
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
