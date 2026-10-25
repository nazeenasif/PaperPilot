---
id: 3
title: Align spec with new designs
stage: spec
date: 2026-10-25
surface: agent
model: claude-opus-5-5
feature: 004-summaries-comparison
branch: 004-summaries-comparison
user: Nazeen Asif
command: /sp.specify (design alignment)
labels: ["design", "navigation", "summary", "comparison", "request-budget"]
links:
  spec: specs/004-summaries-comparison/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/004-summaries-comparison/spec.md
 - specs/004-summaries-comparison/checklists/requirements.md
 - docs/design/summary.png
 - docs/design/compare.png
 - docs/design/library.png
tests:
 - none (specification only)
---

## Prompt

1: A (five sections; the sixth card is a state example, now relabelled in the design). 2: confirm, Q2: A stands; the design now says "uses 5 requests, 1 per aspect". 3: yes, four tabs; library.png is updated to match. 4 passages per section is fine. I'm re-exporting summary.png, compare.png and library.png now; commit them with the spec update.

## Response snapshot

Spec updated:
- **Clarifications:** four new entries — five sections, one request per aspect kept, four header tabs, 4 passages per section.
- **FR-001:** a summary can be opened or started from a paper's card and from the Summarize tab, which lists papers with their saved summaries.
- **Assumptions:** Placement now names the four tabs (Ask, Library, Summarize, Compare); Retrieval sizes now use 4 passages per summary section.
- **Checklist:** the alignment is noted and all 16 items still pass.

The re-exported designs had not landed when first checked: compare.png still said "uses 1 request" and all files were timestamped 12:46:45. The commit therefore waits until the new exports are in place and match the answers.

## Outcome

- ✅ Impact: the spec matches the updated designs; no open markers.
- 🧪 Tests: none (specification).
- 📁 Files: spec.md, checklists/requirements.md, and the three design PNGs once re-exported.
- 🔁 Next prompts: /sp.plan.
- 🧠 Reflection: checking the design files against the spec caught a cost label (1 vs 5 requests) that would otherwise have reached the UI.

## Evaluation notes (flywheel)

- Failure modes observed: the design files changed during the session; their content was verified before committing.
- Graders run and results (PASS/FAIL): spec quality checklist, 16/16 PASS.
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
