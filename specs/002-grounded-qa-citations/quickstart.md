# Quickstart: Grounded Question Answering

Windows, PowerShell, repo root, venv active, Feature 1 library populated
(`python scripts/checkpoint_3_search.py papers`).

## 1. Configure the model

1. Create a free API key in Google AI Studio.
2. In `.env` (never commit it):

```text
LLM_PROVIDER=gemini
LLM_MODEL=<a free-tier Flash model name exactly as shown in AI Studio>
GEMINI_API_KEY=<your key>
# optional
RELEVANCE_THRESHOLD=0.60
LLM_THINKING_LEVEL=
```

3. `python scripts/checkpoint_0_settings.py` — shows `GEMINI_API_KEY = set (hidden)`.

## 2. Calibrate the threshold (no LLM calls)

```powershell
python scripts/calibrate_threshold.py   # writes eval/threshold_calibration.md
```

## 3. Checkpoints

```powershell
python scripts/checkpoint_4_answer.py        # cited answer, not-found, filter, citation checks, secrets
python scripts/checkpoint_5_conversation.py  # follow-up rewrite, probe questions -> eval/probe_answers.md
```

Free-tier rate limits may add waits of up to a minute between calls; that is expected.

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
