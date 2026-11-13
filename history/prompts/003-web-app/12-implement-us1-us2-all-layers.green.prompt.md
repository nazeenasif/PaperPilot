---
id: 12
title: Implement US1 US2 All Layers
stage: green
date: 2026-10-25
surface: agent
model: claude-opus-5-5
feature: 003-web-app
branch: 003-web-app
user: Nazeen Asif
command: /sp.implement
labels: ["us1", "us2", "sse", "highlights", "viewer", "react-pdf", "checkpoint-6"]
links:
  spec: specs/003-web-app/spec.md
  ticket: null
  adr: history/adr/0006-citation-highlight-geometry.md
  pr: null
files:
 - paperpilot/{llm.py,service.py,ingest.py,library.py,store.py,errors.py}
 - api/{routes.py,schemas.py,errors.py,streams.py}
 - frontend/lib/{sentences.ts,reveal.ts,useAsk.ts,geometry.ts}
 - frontend/components/ask/{AskScreen,Composer,ProgressSteps,AnswerView,CitationChip,VerifiedBadge}.tsx
 - frontend/components/source/{SourceViewer,HighlightOverlay,PdfPage}.tsx
 - frontend/app/page.tsx
 - frontend/e2e/{fake-backend.ts,fixtures.ts,pdf.ts,smoke.spec.ts}
 - scripts/checkpoint_6_geometry.py
 - scripts/checkpoint_6_web.py
 - tests/{conftest.py,test_service_events.py,test_llm.py,test_ingest_layout.py,test_library_pdfs.py}
 - tests/api/{test_ask.py,test_passages.py}
 - frontend/tests/{reveal.test.ts,ask.test.tsx,source-viewer.test.tsx}
tests:
 - pytest: 464 passed
 - vitest: 86 passed
 - playwright: US1 and US2 smoke tests pass (desktop and phone)
 - checkpoint_6_geometry.py: 223/223 passages exact (100%)
 - checkpoint_6_web.py ask viewer: PASS, 1 model request (1 planned, 0 retries)
---

## Prompt

the US1 and US2 tasks in every layer (engine, API, frontend), skipping US3–US5 for now. Tests first, one commit per task. Then re-attach the five PDFs, run checkpoint 6's ask and viewer parts (about 1 model request), and stop. Show the checkpoint output and the highlight success rate.

## Response snapshot

T019–T026, T034–T039, T049–T056 done, tests first, one commit per task. Engine: ask(on_event)
and generate(on_retry)/RetryNotice; word boxes per block, align_words across hyphen breaks,
Passage.regions with exact_regions, build_layout, arXiv id; stored PDFs, attach with id/text
check and mismatch marker, get_passage (no parsing), pdf_path, reprocess_paper, store write
lock; geometry checkpoint 223/223 exact. API: POST /api/ask SSE (validation and lock in a
dependency, worker thread bridge), GET /api/passages/{id}, GET /api/papers/{id}/pdf; part ask and
part viewer. Fixed a race (lock released after the final event) found as one flaky failure.
Frontend: sentences/reveal mirroring the engine, Ask screen with progress, staggered reveal,
labelled chips and badge; SourceViewer (react-pdf browser-only, overlay scaled from points,
fallbacks, re-process offer, focus returns to the chip); fake backend and PDF built in code
(K1); smoke tests US1/US2. Re-attached the five PDFs via the engine: all pdf_attached with exact
highlights in 0.3–2.5 s, no embedding. Usage before: 34/50. Checkpoint 6 ask+viewer: PASS, 1
request; highlight success 5/5 (100%), 99% of highlighted words belong to their passage.

## Outcome

- ✅ Impact: ask → verified answer → click a citation → PDF page with exact highlights, end to end.
- 🧪 Tests: pytest 464; vitest 86; Playwright US1/US2 ×2 viewports; checkpoints PASS.
- 📁 Files: see list.
- 🔁 Next prompts: US3–US5 (library screen and uploads, scope/follow-ups, designed failure states and usage meter).
- 🧠 Reflection: the answer's third sentence again generalises across passages (GLUE, E2E, GPT-3) — the F2 pattern; generate took 35 s, above the 15 s median target, on a single sample.

## Evaluation notes (flywheel)

- Failure modes observed: lock-release race; Radix restores focus only to its own triggers; vitest env leakage earlier; test fixture chunk sizes that didn't change the passages.
- Graders run and results (PASS/FAIL): pytest PASS; vitest PASS; playwright PASS; geometry PASS; checkpoint 6 ask+viewer PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
