---
id: 1
title: Specify PDF Ingestion Semantic Search
stage: spec
date: 2026-10-23
surface: agent
model: claude-opus-5-5
feature: 001-pdf-ingest-search
branch: 001-pdf-ingest-search
user: Nazeen Asif
command: /sp.specify
labels: ["spec", "ingestion", "semantic-search", "rag"]
links:
  spec: specs/001-pdf-ingest-search/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/001-pdf-ingest-search/spec.md
 - specs/001-pdf-ingest-search/checklists/requirements.md
tests:
 - none
---

## Prompt

Feature 1: PDF ingestion and semantic search for PaperPilot (see docs/paperpilot-guide.pdf, Phases 0–3).

Goal: a user can add research-paper PDFs to a persistent library and search them by meaning, with every result traceable to its paper, section and page. No LLM is involved in this feature.

User stories:
1. As a researcher, I add a text-based research-paper PDF and it becomes searchable.
2. As a researcher, adding the same PDF twice never creates duplicate data.
3. As a researcher, I search with a natural-language question and get the most relevant passages, each showing paper title, section, page and a similarity score.
4. As a researcher, I can limit a search to one or more selected papers.
5. As a researcher, I can list the papers in my library (title, number of passages) and delete a paper.
6. As a researcher, my library is still there after restarting the program.

Functional requirements:
- Each paper gets a stable ID derived from its file content.
- Title is taken from PDF metadata, falling back to the first suitable text on page 1, then the file name.
- Text is cleaned (hyphenated line breaks joined, whitespace normalized) and read in correct order for two-column layouts.
- Standard section headings (Abstract, Introduction, Related Work, Background, Method(s)/Methodology/Approach, Experiments, Results, Discussion, Limitations, Conclusion(s)) are detected; text before the first heading is "Front Matter".
- Everything from the References section onward is excluded.
- Text is split into passages of roughly 220 words with ~40 words of overlap, configurable via environment variables; passages never cross a section boundary; tiny leftovers (<30 words) are dropped; each passage records its starting page.
- A PDF with no extractable text (e.g. scanned) produces a clear error, not a crash.
- Search returns the top k passages (default 6, configurable) with a similarity score between 0 and 1.

Out of scope: LLM answers, summaries, comparison, UI, API, OCR, table/equation extraction.

Acceptance criteria (matching the guide's Checkpoints 0–3):
- Settings load and print without errors.
- On 5 test arXiv papers (Attention Is All You Need, BERT, RAG, LoRA, Lost in the Middle): titles and sections look correct and no reference-list text appears.
- A typical conference paper yields roughly 40–120 passages averaging close to 200 words, and random passages read sensibly on their own.
- Searching "what dataset was used for evaluation?" returns passages genuinely about evaluation data, with scores roughly 0.45–0.8.
- A paper-filtered search returns results only from that paper.
- Results persist after restarting Python.
- Known limitations (regex heading detection, heuristic titles, messy equations/tables, scanned PDFs) are documented.

## Response snapshot

Created branch 001-pdf-ingest-search and wrote spec.md with 5 prioritized user stories
(add+search P1, no duplicates P1, persistence P1, filtered search P2, list/delete P3), 11 edge
cases, FR-001..FR-020, 4 key entities, SC-001..SC-009, assumptions, and out-of-scope list. No
clarification markers needed. Quality checklist passed on first iteration.
create-new-feature.ps1 failed at its final step (3-argument Join-Path unsupported in
PowerShell 5.1) after creating the branch and spec file.

## Outcome

- ✅ Impact: Feature 1 spec ready for planning.
- 🧪 Tests: none (spec stage)
- 📁 Files: specs/001-pdf-ingest-search/spec.md, specs/001-pdf-ingest-search/checklists/requirements.md
- 🔁 Next prompts: /sp.clarify (optional) or /sp.plan
- 🧠 Reflection: Merged user stories 1 and 3 into one P1 MVP slice since adding without searching is not independently valuable.

## Evaluation notes (flywheel)

- Failure modes observed: create-new-feature.ps1 Join-Path incompatibility with Windows PowerShell 5.1; create-phr.sh absent.
- Graders run and results (PASS/FAIL): spec quality checklist PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): fix Join-Path in create-new-feature.ps1 to nested two-argument calls.
