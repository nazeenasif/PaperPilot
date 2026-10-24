# Contract: question answering (Python API)

**Feature**: 002-grounded-qa-citations. No network API (out of scope). Types are in
[data-model.md](../data-model.md).

## `paperpilot.service.ask`

```python
ask(question: str, paper_ids: list[str] | None = None, k: int | None = None,
    history: list[Turn] | None = None) -> Answer
```

- `k` defaults to `TOP_K`; `paper_ids=None` or `[]` searches the whole library.
- `history`: earlier turns, oldest first; only the last 6 are used; empty/None → no rewrite.
- Never raises for "no answer": unsupported questions return `Answer(text=NOT_FOUND, ...)`.

| Error | When |
|---|---|
| `EmptyQueryError` | question empty or whitespace |
| `UnknownPaperError` | a filter ID is not in the library (from Feature 1 search) |
| `SettingsError` | `LLM_MODEL`/`GEMINI_API_KEY` missing, unknown `LLM_PROVIDER` (message names the setting, never a value) — raised only when the model is actually needed |
| `LLMError` | provider still failing after retries, non-retryable provider error, or truncated/empty output (one readable line, key scrubbed) |

## `paperpilot.prompts` (pure; unit-tested offline)

- `NOT_FOUND: str` — `"I couldn't find that in the selected papers."`
- `SYSTEM_INSTRUCTION: str`, `REWRITE_INSTRUCTION: str`
- `build_answer_prompt(question: str, passages: list[NumberedPassage]) -> str`
- `build_rewrite_prompt(history: list[Turn], question: str) -> str` (uses last 6 turns)
- `clean_rewrite(reply: str) -> str`
- `is_not_found(reply: str) -> bool`
- `extract_citations(text: str) -> list[int]`
- `check_citations(text: str, passage_count: int) -> CitationReport`

## `paperpilot.llm` (the only module that talks to an LLM)

- `generate(system: str, prompt: str) -> LLMReply` — provider and model from settings;
  retries per research R3; raises `SettingsError` or `LLMError`.
- `PROVIDERS: dict[str, Callable]` — registry; `"gemini"` only in this feature.
