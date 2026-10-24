---
id: 2
title: Resolve Streaming And PDF Attach
stage: spec
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 003-web-app
branch: 003-web-app
user: Nazeen Asif
command: /sp.specify (clarification answer)
labels: ["spec", "clarification", "animation", "reduced-motion", "pdf-attach"]
links:
  spec: specs/003-web-app/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/003-web-app/spec.md
 - specs/003-web-app/checklists/requirements.md
tests:
 - none (specification)
---

## Prompt

A - Adding a paper that is already in the library but has no stored PDF saves the PDF without re-parsing or re-embedding, and reports "PDF attached" instead of "already present". The verified answer appears with a short entrance animation (sentences fade in in sequence, then citation chips, then the verified badge), completing in under 500 ms; it is never paced to imitate typing. Users who prefer reduced motion see it appear instantly.

## Response snapshot

Added a Clarifications session. FR-011: no answer text before citations are checked; entrance
animation (sentences, then chips, then badge) under 500 ms, never typing-paced, instant with
reduced motion; replaces the mock-up's Streaming card. US1 scenario 5 and SC-011 added. PDF
attach: US3 scenario 4 ("PDF attached", no parse/embed), FR-018 split into already present vs PDF
attached, US2 scenario 5 and assumptions point to it, Upload job outcomes and SC-004 updated,
dependency noted. A duplicate copy of the animation sentence that had been appended to the old
FR-011 line on disk was merged into the single rewritten FR-011. Checklist: all items pass.

## Outcome

- ✅ Impact: spec complete with no open markers.
- 🧪 Tests: none.
- 📁 Files: spec.md, checklists/requirements.md
- 🔁 Next prompts: /sp.clarify (optional) or /sp.plan.
- 🧠 Reflection: rejecting streaming keeps unverified text off screen while the animation keeps the mock-up's feel.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): checklist PASS (all items)
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
