---
id: 9
title: Analyze Web App Artifacts
stage: misc
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 003-web-app
branch: 003-web-app
user: Nazeen Asif
command: /sp.analyze
labels: ["analyze", "consistency", "coverage", "constitution", "security"]
links:
  spec: specs/003-web-app/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - none modified (read-only analysis)
tests:
 - none
---

## Prompt

/sp.analyze (no arguments)

## Response snapshot

Read-only analysis of spec.md, plan.md, tasks.md against constitution v1.3.0. 18 findings:
CRITICAL K1 (e2e PDF fixtures would be committed; Principle VI and .gitignore *.pdf); HIGH A1
(CORS does not stop simple cross-site POSTs — multipart upload and empty-body reprocess can be
triggered by any web page; add an Origin/custom-header check); MEDIUM G1 (SC-005 never asserted),
G2 (SC-004 60 s check optional), G3 (empty-library edge case untasked), G4 (rate_limited
daily:true → daily-limit screen untested), I1 (spec still calls the UTC reset unverified), U1
(T065 merges test and code), U2 (T002 deps not justified in R1); LOW G5, G6, I2, I3, I4, A2, U3,
U4, U5. Coverage: 51 requirements, 71 tasks, 100% with ≥ 1 task, 4 partial. Recommended fixing
K1 and A1 before /sp.implement; offered concrete remediation for the top 9.

## Outcome

- ✅ Impact: one constitution conflict and one security gap found before implementation.
- 🧪 Tests: none.
- 📁 Files: none modified.
- 🔁 Next prompts: approve remediation edits (spec FR-002a/SC-012, contract, tasks), then /sp.implement.
- 🧠 Reflection: "localhost only + CORS" reads as secure but leaves CSRF-style simple requests open; an Origin check closes it.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): coverage 100% (4 partial); 1 critical
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
