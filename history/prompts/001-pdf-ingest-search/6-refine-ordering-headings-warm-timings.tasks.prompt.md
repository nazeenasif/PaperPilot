---
id: 6
title: Refine Ordering Headings Warm Timings
stage: tasks
date: 2026-10-23
surface: agent
model: claude-opus-5-5
feature: 001-pdf-ingest-search
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: none (direct request)
labels: ["tasks", "headings", "reading-order", "timings"]
links:
  spec: specs/001-pdf-ingest-search/spec.md
  ticket: null
  adr: history/adr/0001-local-retrieval-stack.md, history/adr/0002-passage-identity-and-chunking.md
  pr: null
files:
 - specs/001-pdf-ingest-search/tasks.md
 - specs/001-pdf-ingest-search/research.md
 - specs/001-pdf-ingest-search/plan.md
 - specs/001-pdf-ingest-search/contracts/library-api.md
 - history/adr/0001-local-retrieval-stack.md
 - history/adr/0002-passage-identity-and-chunking.md
tests:
 - none
---

## Prompt

Update tasks.md (and research.md R7 if needed):
1. T012/T021: replace the +1 sequence guard with "greater than the previous numbered heading and at most 2 higher". Keep the "7 Results Table after 2" rejection test and add a test where heading 4 is missing and "5 Training" and "6 Results" are still detected after 3.
2. T031: load the embedding model once before any timed add or search, and print model load time separately; the SC-010 and SC-011 checks use warm timings only.
3. T011/T020: treat a block wider than 60% of the page as a band divider: order two-column blocks above it (left then right), then the wide block, then the blocks below it. Add a test with a full-width caption in the middle of a two-column page.

## Response snapshot

tasks.md: T011 adds top-banner and mid-page caption band tests and all-wide single-column
case; T012 adds missing-heading-4 case, "not greater" rejection, keeps "7 after 2"; T020/T021
describe band ordering and the >prev, ≤prev+2 guard; T028 adds store.load_model() returning
load seconds; T031 warms model first, prints load time separately, checks warm timings;
T046 limitation list updated. research.md R2, R7, R13 updated. Kept plan.md, ADR-0001,
ADR-0002 and contracts consistent (old "+1" and "treated as left column" wording removed).

## Outcome

- ✅ Impact: Heading detection tolerates one missed heading; mid-page full-width blocks no longer break column order; timing checks are fair.
- 🧪 Tests: none run; test task descriptions extended.
- 📁 Files: tasks.md, research.md, plan.md, contracts/library-api.md, ADR-0001, ADR-0002
- 🔁 Next prompts: /sp.implement starting at T001
- 🧠 Reflection: Band ordering also makes single-column pages correct with no special case.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): stale-term grep ("+1", "left column") clean PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
