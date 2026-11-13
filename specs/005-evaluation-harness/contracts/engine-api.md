# Contract: engine changes for Feature 5

Each change defaults to today's behaviour; existing tests must pass unchanged (FR-026, research R12).

```python
@dataclass(frozen=True)
class Retrieval:                      # service
    passages: list[SearchResult]
    gate_score: float | None          # the top vector score; None when nothing was found

def ask(question, paper_ids=None, k=None, history=None, on_event=None,
        retrieve: Callable[[str, int, list[str] | None], Retrieval] | None = None) -> Answer
```
- Default `retrieve`: `library.search(standalone, k=k, paper_ids=paper_ids)` with `gate_score` = top
  score: identical to today. The gate compares `gate_score` with `RELEVANCE_THRESHOLD`.

```python
def generate(system, prompt, on_retry=None, task="answer", model: str | None = None) -> LLMReply   # llm
```
- `model` defaults to `LLM_MODEL`; the request is counted, retried and limited as any other.
- `OUTPUT_TOKENS["judge"] = 8192`.

```python
def summarize(..., save: bool = True) -> Summary      # service
def compare(..., save: bool = True) -> Comparison
```
- `save=False`: no saved result is read for reuse or written; the run stays out of the library.

**Settings** (`config.Settings`, read from `.env`):

| Setting | Default | Effect |
|---|---|---|
| `USAGE_DIR` | `LIBRARY_DIR` | where `usage.sqlite3` lives |
| `EMBED_PREFIX` | `false` | embed `"{title}. {section}. {text}"`; stored text unchanged |
| `SCOPE_RULE` | `true` | the scope rule in the section, TL;DR and row instructions |
| `EVAL_JUDGE_MODEL` | `google/gemma-4-31b-it:free` | the judge (the harness only) |
| `EVAL_RESERVE` | `10` | requests a session never spends (the harness only) |

The harness is a separate package, `evaluation/`, importing `paperpilot` but never imported by it,
by the API or by the frontend.
