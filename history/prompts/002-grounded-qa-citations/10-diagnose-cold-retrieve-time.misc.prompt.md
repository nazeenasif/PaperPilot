---
id: 10
title: Diagnose Cold Retrieve Time
stage: misc
date: 2026-10-24
surface: agent
model: claude-opus-5-5
feature: 002-grounded-qa-citations
branch: 002-grounded-qa-citations
user: Nazeen Asif
command: none (direct request)
labels: ["performance", "startup", "diagnosis", "checkpoint-4"]
links:
  spec: specs/002-grounded-qa-citations/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - scripts/checkpoint_4_answer.py
tests:
 - scratchpad timing script, run normally and with HF_HUB_OFFLINE=1
 - scripts/checkpoint_4_answer.py: PASS, 1 LLM request
---

## Prompt

Diagnose the 167 s retrieve time before adding any warm-up. In a separate script, time: (a) store.load_model() alone, (b) opening the library, (c) the first search, (d) a second search. Run it twice: once normally, once with HF_HUB_OFFLINE=1 set. Report the numbers. If offline mode removes the delay, set HF_HUB_OFFLINE=1 in .env.example with a comment (first run must download the model with it unset), document it in the quickstart, and record the finding in research.md. Only then add the warm-up to checkpoint 4, printing cold timings separately.

## Response snapshot

Timing (fresh processes): normal — import paperpilot 6.97 s, (a) load_model 25.58 s, (b) open
library 0.61 s, (c) first search 0.29 s, (d) second search 0.07 s, total 33.51 s; offline —
5.94 / 22.52 / 0.34 / 0.19 / 0.05 s, total 29.05 s. Offline mode saves ~3 s, so it was not
adopted (.env.example, quickstart, research unchanged). Breakdown of (a): import torch 5.69 s,
import sentence_transformers 17.66 s, build model from cache 2.64 s — the cost is Python import,
not network. The 167 s did not reproduce (earlier checkpoint-3 loads were 2–8 s); likely
first-import slowness after package changes (e.g. antivirus scanning), unverified. Added a
warm-up to checkpoint 4 (model import+load and library open+first search printed as "Cold:"
lines). Rerun: cold model 24.6 s, cold library+search 0.84 s, answer retrieve 0.04 s, generate
3.11 s, 1 LLM request, PASS.

## Outcome

- ✅ Impact: answer timings now reflect per-question cost; root cause identified as import time.
- 🧪 Tests: checkpoint 4 PASS.
- 📁 Files: scripts/checkpoint_4_answer.py
- 🔁 Next prompts: US2 (T015–T020); the UI feature must load the model at startup.
- 🧠 Reflection: measuring sub-steps separated a plausible cause (network) from the real one (imports).

## Evaluation notes (flywheel)

- Failure modes observed: one-off 167 s cold start not reproducible.
- Graders run and results (PASS/FAIL): checkpoint 4 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): if cold imports stay slow, add the venv folder to antivirus exclusions and re-measure.
