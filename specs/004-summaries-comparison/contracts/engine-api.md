# Contract: Engine API additions (Feature 4)

Plain Python, typed, in the existing modules (research R7). Nothing here talks to the model
except through `llm.generate`.

## `paperpilot.service`

```python
def summarize(
    paper_id: str,
    regenerate: bool = False,
    retry_parts: list[str] | None = None,
    on_event: Callable[[str, dict], None] | None = None,
) -> Summary
```

- Without `regenerate`/`retry_parts`, returns the **current** saved summary with **zero** model
  requests if there is one; otherwise generates.
- `regenerate=True`: generates a new summary; the saved one is replaced only on completion.
- `retry_parts`: re-runs only the named parts (`"tldr"` is a part of its own); other parts come
  from the saved summary. A regenerated section leaves the TL;DR marked `built_without` it until
  `"tldr"` is retried too.
- Before the first request: computes the `RequestPlan` and raises `DailyLimitError` if
  `llm.usage().remaining < plan.max_requests` (no request sent).
- Per facet: `facet_results(facet, paper_id)` (research R2: `library.search`, this paper only, in the
  sections the facet may search; up to 4 passages, and Limitations searches twice); below threshold → part
  `not_reported` (`below_threshold`) with no request; else one `llm.generate` call, then
  `review_reply(text, allowed=<this facet's numbers>)`.
- TL;DR: only if ≥ 1 section is `verified`; one `llm.generate` call on the verified sections'
  text; checked by `prompts.check_tldr`.
- Per-part `LLMError` with reason `cut_off`/`empty` → that part `failed`; `DailyLimitError`,
  `RateLimitedError`, `LLMError` with `busy`/`timeout`/`unreachable` (all retries spent) or a
  configuration reason → the run stops, remaining parts `not_started`, finished parts saved
  (research R8).
- Events (`on_event`): `plan`, `progress` {part, step, passages?}, `retry_wait` {part, …},
  `part` {Part} after its check. No event carries unchecked text.
- Raises `UnknownPaperError`, `SettingsError`, `DailyLimitError` (pre-check only; later limits end
  the run and are reported in the parts).

```python
def compare(
    paper_ids: list[str],
    aspects: list[str],
    regenerate: bool = False,
    retry_aspects: list[str] | None = None,
    on_event: Callable[[str, dict], None] | None = None,
) -> Comparison
```

- Validates 2–4 distinct known papers (`ValueError` → API `invalid_request`; `UnknownPaperError`)
  and a non-empty subset of `prompts.ASPECTS` in fixed order.
- Per aspect: per paper `library.search(aspect_query, k=3, paper_ids=[p])`; de-duplicated,
  numbered once per comparison; one `llm.generate` call with `prompts.build_row_prompt`;
  `prompts.parse_row` → malformed → row `failed` (`malformed`); else each cell through
  `review_reply(cell_text, allowed=<that paper's numbers in this row>)`.
- Same saving, plan, pre-check, stop rules and events as `summarize` (parts are cells; `progress`
  carries `part: "<aspect>"`).

```python
def saved_summary(paper_id: str) -> Summary | None          # current or stale; never generates
def saved_comparison(paper_ids: list[str], aspects: list[str]) -> Comparison | None
def summary_plan(paper_id: str, retry_parts: list[str] | None = None) -> RequestPlan
def comparison_plan(paper_ids: list[str], aspects: list[str], retry_aspects: list[str] | None = None) -> RequestPlan
```

`review_reply(text, passage_count=None, allowed=None)` — existing; `allowed` added
(research R1). `ask()` is unchanged in behaviour.

## `paperpilot.prompts`

```python
SUMMARY_PROMPT_VERSION: int                    # raised when facet/aspect prompts or check rules change
NOT_REPORTED = "Not reported in the retrieved passages."
FACETS: dict[str, Facet]                       # problem, method, data, results, limitations
ASPECTS: dict[str, Facet]                      # problem, method, datasets, results, limitations
SECTION_INSTRUCTION, TLDR_INSTRUCTION, ROW_INSTRUCTION: str

def format_passages(passages: list[NumberedPassage]) -> str           # shared with build_answer_prompt
def build_section_prompt(facet: str, passages: list[NumberedPassage]) -> str
def build_tldr_prompt(sections: list[tuple[str, str]]) -> str          # (label, verified text)
def build_row_prompt(aspect: str, papers: list[tuple[str, str, list[NumberedPassage]]]) -> str
                                                                     # (label, title, passages)
def parse_row(reply: str, labels: list[str]) -> dict[str, str]        # raises RowFormatError
def check_citations(text: str, passage_count: int | None = None, allowed: set[int] | None = None) -> CitationReport
def check_tldr(text: str, sections: list[VerifiedSection]) -> TldrCheck
```

`TldrCheck`: `ok: bool`, `not_found: bool`, `citations: CitationReport`, `sources: list[list[str]]`
(per sentence), `problems: list[str]` (each failing rule, e.g. "sentence 2 cites passage 9, which
no verified section cites").

## `paperpilot.library`

```python
def save_result(kind: str, key: ResultKey, result: dict) -> None
def load_result(kind: str, key: ResultKey) -> tuple[dict, str | None] | None   # (result, stale_reason)
def forget_results(paper_id: str) -> int                                       # rows removed
def passage_fingerprint(paper_id: str) -> str
```

`delete_paper` and `reprocess_paper` call `forget_results` (research R6).

## `paperpilot.errors`

`RowFormatError(PaperPilotError)` — a comparison row's reply is not the expected JSON; caught by
`service.compare`, never raised to callers.
