---
id: 5
title: Switch to OpenAI-Compatible Provider
stage: plan
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: none (direct request)
labels: ["plan", "openrouter", "openai", "adr", "retries", "provider"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: history/adr/0003-llm-boundary-and-retry-policy.md, history/adr/0004-grounding-and-citation-validation.md
  pr: null
files:
 - specs/002-grounded-qa-citations/spec.md
 - specs/002-grounded-qa-citations/checklists/requirements.md
 - specs/002-grounded-qa-citations/research.md
 - specs/002-grounded-qa-citations/plan.md
 - specs/002-grounded-qa-citations/data-model.md
 - specs/002-grounded-qa-citations/contracts/answer-api.md
 - specs/002-grounded-qa-citations/quickstart.md
 - .env.example
 - history/adr/0003-llm-boundary-and-retry-policy.md
 - history/adr/0004-grounding-and-citation-validation.md
tests:
 - pytest: 183 passed (after removing google-genai)
---

## Prompt

Change of LLM provider for Feature 2, before /sp.tasks: replace the Gemini-specific design with one OpenAI-compatible client (the openai package) configured by LLM_BASE_URL, an API key and LLM_MODEL; default provider is OpenRouter with a pinned :free model. Remove google-genai from the environment and the plan. Keep: retries honouring the server's retry-after (OpenRouter returns 429 with X-RateLimit headers), a clear error when output is cut off (finish_reason "length", since reasoning models spend output tokens on reasoning), and the key never appearing in errors or logs. Note OpenRouter free limits (20/min, 50/day under $10 lifetime credits, 1,000/day after) in research.md, and that evaluation runs need the higher limit. Update spec FRs, research, plan, data-model, contracts, quickstart and .env.example. Then create the two ADRs (llm-boundary-and-retry-policy, grounding-and-citation-validation) reflecting the new design.

## Response snapshot

Verified OpenRouter limits/errors/reasoning docs (20/min; 50/day <$10 credits, 1,000/day
after; 429 with X-RateLimit-Limit/Remaining/Reset, Retry-After when hinted; 200 responses can
carry an error object and no choices; reasoning counts against max_tokens, finish_reason
"length" with empty content; reasoning.effort/max_tokens caps) and listed models (17 :free,
all reasoning) → pinned google/gemma-4-31b-it:free. Uninstalled google-genai; openai 3.37.0
already present; inspected client params, errors, usage (reasoning_tokens), finish_reason.
Updated spec (clarification, FR-013 rewritten with LLM_PROVIDER/LLM_BASE_URL/LLM_API_KEY/
LLM_MODEL, FR-014 retry hints, new FR-014a cut-off, 2 edge cases, assumptions, out of scope),
checklist, research (R1–R4 rewritten, R10, new R12 limits), plan (constitution check flags
Principle III "Gemini or Groq" conflict with amendment recommended), data-model, contract,
quickstart, .env.example. Created ADR-0003 and ADR-0004. Noted untracked scratch_openrouter.py
(no key; uses OPENROUTER_API_KEY vs designed LLM_API_KEY).

## Outcome

- ✅ Impact: Feature 2 design is provider-neutral; ADRs recorded.
- 🧪 Tests: 183 passed.
- 📁 Files: 7 spec docs, .env.example, 2 ADRs.
- 🔁 Next prompts: /sp.constitution to amend Principle III; then /sp.tasks.
- 🧠 Reflection: All current free models reason, so the length guard is essential, not optional.

## Evaluation notes (flywheel)

- Failure modes observed: constitution names specific providers, so a provider change needs an amendment.
- Graders run and results (PASS/FAIL): stale-reference grep clean (only historical notes); pytest PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
