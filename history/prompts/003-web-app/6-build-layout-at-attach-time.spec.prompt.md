---
id: 6
title: Build Layout At Attach Time
stage: spec
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 003-web-app
branch: 003-web-app
user: Nazeen Asif
command: direct request
labels: ["spec", "amendment", "highlights", "attach", "reprocess"]
links:
  spec: specs/003-web-app/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/003-web-app/spec.md
 - specs/003-web-app/research.md
 - specs/003-web-app/data-model.md
 - specs/003-web-app/plan.md
 - specs/003-web-app/contracts/web-api.md
 - specs/003-web-app/contracts/engine-api.md
 - specs/003-web-app/quickstart.md
 - specs/003-web-app/checklists/requirements.md
tests:
 - none (specification)
---

## Prompt

Amend the FR-018 handling: build highlight layout when a PDF is attached (in the ingest worker, as part of the attach job with its own progress step), not on first citation open. Keep the check that every passage ID and text matches what is stored. If the check fails, store no layout; the viewer then opens the cited page without a highlight and offers "Re-process paper for exact highlights". Update the spec, research and data model. Commit.

## Response snapshot

Spec: clarification amendment note; FR-018 (attach = store PDF + "Mapping highlights" step,
parse and chunk only, layout only if ids and texts match, otherwise none; still "PDF attached");
new FR-018a (re-process from stored PDF, passages replaced only after success); FR-013 offers
the re-process action on a mismatch; US2 scenarios 6–7; US3 scenario 4; SC-004 attach within
10 s incl. mapping; entities and assumptions. Research R4: attach-time mapping, re-process job,
passage-id change note, lazy design recorded as superseded; R14 attach/reprocess functions.
Data model: highlight status (exact, mismatch, no_pdf) with a mismatch marker file, mapping
phase, reprocess job kind and outcome, highlights field, state transitions. For consistency also
updated the contracts (attach job phases, POST /api/papers/{id}/reprocess, busy_job,
layout_reason mismatch + can_reprocess, get_passage never parses), plan, quickstart and
checklist.

## Outcome

- ✅ Impact: opening a citation is always a plain read; attach shows its mapping work as progress.
- 🧪 Tests: none.
- 📁 Files: see list.
- 🔁 Next prompts: ADRs; /sp.tasks.
- 🧠 Reflection: re-processing can change passage ids, so on-screen answers need a "passage no longer in the library" state.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): no stale "lazy" wording left except the recorded superseded design
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
