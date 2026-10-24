# Quickstart: Grounded Question Answering

Windows, PowerShell, repo root, venv active, Feature 1 library populated
(`python scripts/checkpoint_3_search.py papers`).

## 1. Configure the model

1. Create an API key at https://openrouter.ai/keys (free models need no credits).
2. In `.env` (never commit it):

```text
LLM_PROVIDER=openrouter
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=<your key>
LLM_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free   # alternative: google/gemma-4-31b-it:free
# optional
RELEVANCE_THRESHOLD=0.60
LLM_REASONING_EFFORT=
```

3. `python scripts/checkpoint_0_settings.py` — shows `LLM_API_KEY = set (hidden)`.

Any other OpenAI-compatible provider works by changing `LLM_PROVIDER`, `LLM_BASE_URL`,
`LLM_API_KEY` and `LLM_MODEL`.

## 2. Calibrate the threshold (no LLM calls)

```powershell
python scripts/calibrate_threshold.py   # writes eval/threshold_calibration.md
```

## 3. Checkpoints

```powershell
python scripts/checkpoint_4_answer.py        # cited answer, not-found, filter, citation checks, secrets
python scripts/checkpoint_5_conversation.py  # follow-up rewrite, probe questions -> eval/probe_answers.md
```

Free models allow 20 requests/minute and 50 requests/day (1,000/day after $10 of lifetime
credits). Waits of up to a minute between calls are expected; one full checkpoint run fits
in the daily limit, repeated runs and evaluation runs need the higher limit. If the output is
cut off by reasoning, set `LLM_REASONING_EFFORT=low`.

## 4. Unit tests (offline, no key needed)

```powershell
pytest
```

## 5. Use from Python

```python
from paperpilot.service import ask, Turn

a = ask("Which dataset was the Transformer trained on for English-German translation?")
print(a.text)
for p in a.passages:
    print(f"[{p.number}] {p.title} — {p.section}, p. {p.page}")

first = ask("What is LoRA?")
b = ask("What are its limitations?", history=[Turn("user", "What is LoRA?"), Turn("assistant", first.text)])
print(b.standalone_question)   # e.g. "What are the limitations of LoRA?"
print(b.text)
```
