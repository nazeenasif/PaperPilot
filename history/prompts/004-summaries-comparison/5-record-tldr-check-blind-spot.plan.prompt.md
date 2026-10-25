---
id: 5
title: Record TL;DR check blind spot
stage: plan
date: 2026-10-25
surface: agent
model: claude-opus-5-5
feature: 004-summaries-comparison
branch: 004-summaries-comparison
user: Nazeen Asif
command: research and limitations update
labels: ["tldr-check", "faithfulness", "known-limitations"]
links:
  spec: specs/004-summaries-comparison/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/004-summaries-comparison/research.md
 - docs/known-limitations.md
tests:
 - none (documentation)
---

## Prompt

Add to research.md and docs/known-limitations.md: the TL;DR check catches uncited sentences, citations outside the verified sections, and numbers absent from the cited sections; it cannot catch a non-numeric claim attached to a valid citation (the F1 pattern). Detecting that is assigned to the evaluation feature's faithfulness judge.

## Response snapshot

**research.md, R3:** added "What the check catches, and what it cannot".
- It catches uncited sentences, citations to passages no verified section cites, and numbers absent from the cited sections.
- It cannot catch a non-numeric claim attached to a valid citation. This is the F1 pattern from `eval/probe_notes.md`: "Wq and Wv" cited to [2] while only [1] says it, which passed Feature 2's answer validation.
- Sections and comparison cells share this blind spot, since they use the same validator.
- Detection is assigned to the evaluation feature's faithfulness judge; until then, checkpoint 7's hand check covers it.

**docs/known-limitations.md:** new section "Summaries and comparison (Feature 4, planned)" with the same limitation. It cross-references the existing "A valid citation does not prove the passage supports the claim" entry under Question answering.

## Outcome

- ✅ Impact: the TL;DR check's limits are documented where planning and users will see them.
- 🧪 Tests: none (documentation).
- 📁 Files: research.md, docs/known-limitations.md.
- 🔁 Next prompts: /sp.adr, then /sp.tasks.
- 🧠 Reflection: the code check covers what can be decided mechanically; claim support needs the passage content, so it belongs to the faithfulness judge.

## Evaluation notes (flywheel)

- Failure modes observed: none.
- Graders run and results (PASS/FAIL): n/a
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
