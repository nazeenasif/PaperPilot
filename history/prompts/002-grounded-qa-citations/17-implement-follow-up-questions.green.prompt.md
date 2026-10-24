---
id: 17
title: Implement Follow-Up Questions
stage: green
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: /sp.implement
labels: ["us4", "follow-up", "rewrite", "checkpoint-5"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: history/adr/0004-grounding-and-citation-validation.md
  pr: null
files:
 - tests/test_prompts.py
 - tests/test_service.py
 - paperpilot/prompts.py
 - paperpilot/service.py
 - scripts/checkpoint_5_conversation.py
 - specs/002-grounded-qa-citations/tasks.md
tests:
 - pytest: 305 passed
 - scripts/checkpoint_5_conversation.py: PASS, 5 LLM requests (budget 12)
---

## Prompt

T024–T028 (US4 follow-up questions). Tests first, commit after each task. Run checkpoint 5, and for each follow-up show: the original question, the rewritten standalone query, rewrite_fallback_reason, the answer with citations, and the request count. Stop.

## Response snapshot

T024 706120d rewrite prompt tests (red: missing REWRITE_INSTRUCTION). T025 d36a883 service
tests (3 red; no-history guard green). T026 9416da1 REWRITE_INSTRUCTION, HISTORY_TURNS=6,
build_rewrite_prompt (User/Assistant labels, last 6 turns, question last), clean_rewrite
(first line, prefix and quotes stripped). T027 8a56f78 rewrite step in ask(): standalone used
for search and answer prompt; LLMError → rewrite_failed, empty → rewrite_empty; explicit
rewrite_applied flag (not inferred from text equality). T028 checkpoint_5_conversation.py
(reuses checkpoint 4 helpers). Run: "What is LoRA?" → not-found (only 2 passages ≥ 0.59, top
0.618 — short "What is X?" queries score low); "What are its limitations?" → "What are the
limitations of LoRA?", cited [1], 2 requests; "How does that method reduce the number of
trainable parameters?" → "How does LoRA reduce the number of trainable parameters?", cited
[1, 2, 5, 6], 2 requests. Verified by search (0 requests) that every claim appears in its
cited passage; "e.g., Wq and Wv" slightly over-specifies passage [2]. Median generate of
answered questions 9.2 s; 5 requests total.

## Outcome

- ✅ Impact: US4 complete; follow-ups resolve "its" and "that method" to LoRA.
- 🧪 Tests: 305 passed; checkpoint 5 PASS.
- 📁 Files: see list.
- 🔁 Next prompts: decide on the "What is LoRA?" false not-found; US5 (T029–T031).
- 🧠 Reflection: rewriting worked even when the previous assistant turn was the not-found sentence, because the user turn named LoRA.

## Evaluation notes (flywheel)

- Failure modes observed: short definitional question scored below most passages (false not-found).
- Graders run and results (PASS/FAIL): pytest PASS; checkpoint 5 PASS; manual claim check 4/4 supported
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): add "What is LoRA?" to the calibration on-topic set and the probe notes; test title/section prefixes (experiment 3).
