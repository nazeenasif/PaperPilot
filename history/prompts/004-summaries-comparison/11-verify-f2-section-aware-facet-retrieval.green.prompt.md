---
id: 11
title: Verify F2, section-aware facet retrieval
stage: green
date: 2026-11-04
surface: agent
model: claude-opus-5-5
feature: 004-summaries-comparison
branch: 004-summaries-comparison
user: Nazeen Asif
command: follow-up to the facet probe
labels: ["retrieval", "faithfulness", "facet-probe", "related-work"]
links:
  spec: specs/004-summaries-comparison/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - paperpilot/store.py
 - paperpilot/library.py
 - paperpilot/prompts.py
 - paperpilot/service.py
 - scripts/probe_facets.py
 - eval/facet_probe.md
 - eval/probe_notes.md
 - specs/004-summaries-comparison/research.md
 - specs/004-summaries-comparison/contracts/engine-api.md
tests:
 - tests/test_facet_retrieval.py
 - tests/test_summarize.py
---

## Prompt

Q1: yes, that's the case. Verify it against the stored passages using the saved checkpoint6_ask_viewer.txt output (0 requests) and update the note.

Q2: section-aware facet retrieval, one change at a time, rerunning the facet probe (0 requests) after each and committing each separately:
1. Exclude Related Work and Front Matter passages from every facet's search.
2. Problem: restrict to Abstract and Introduction; fall back to the whole paper if neither exists.
3. Limitations: 2 passages from sections named Limitations, Discussion or Conclusion (if any), plus 2 from a whole-paper search, de-duplicated.
Add a column to the probe for Related Work passages per facet (target 0). Record in research.md why Related Work is excluded: it describes other papers' work, so citing it in this paper's summary is a faithfulness hazard that citation checks can't catch. Unit tests first for the filtering and fallback. Show the probe table after each step and stop.

## Response snapshot

Q1: the saved file is no longer on disk, but its text survives in the session transcript. It is the 2026-10-24 run, a different run from the sentence in the note, with the same claim in different words ("often with fewer" rather than "far fewer"). Both list the same six passages, and today's search reproduces them with the same scores. [4]'s "matches or exceeds" covers GPT-3 175B only, so F2 is confirmed in both runs; the note now covers both.

Q2: three commits. Related Work passages 6 -> 0 with every gate ok after step 1. Problem marks 4/4 on all five papers after step 2, but LoRA's top score falls to 0.573, under the 0.58 gate, so its Problem section would read Not reported although passage p.1 states the problem. Gate and queries left unchanged for the researcher to decide. Limitations has no MISS after step 3; Attention, BERT and LoRA read 3 passages because their Conclusion holds one. A paper with no named section reads 4 from the whole paper (the request did not state this case).

Tests: pytest 703 passed. Model requests: 0.

## Outcome

- ✅ Impact: summaries no longer read Related Work or Front Matter; Problem and Limitations read the sections they should. SUMMARY_PROMPT_VERSION 4, so saved summaries show as earlier.
- 🧪 Tests: tests/test_facet_retrieval.py new, written first; tests/test_summarize.py updated.
- 📁 Files: see the list above.
- 🔁 Next prompts: decide how the gate treats restricted searches; comparison aspects should apply the same exclusion.
- 🧠 Reflection: restricting a search lowers its top score, while the gate was calibrated on unrestricted searches, so the two rules interact.

## Evaluation notes (flywheel)

- Failure modes observed: LoRA Problem falls below the gate after restriction; the saved file differed from the run the note quoted; the first full pytest run hit a time limit and was rerun.
- Graders run and results (PASS/FAIL): pytest PASS; facet probe Related Work target PASS; facet probe gate 24 of 25 ok.
- Prompt variant (if applicable): SUMMARY_PROMPT_VERSION 4
- Next experiment (smallest change to try): gate a restricted facet on its whole-paper top score, then rerun the probe.
