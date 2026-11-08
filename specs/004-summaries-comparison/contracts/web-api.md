# Contract: Web API additions (Feature 4)

Extends `specs/003-web-app/contracts/web-api.md`. Same base URL, origin rules, `X-PaperPilot: 1`
on writes, error body `{"kind": …}` and SSE conventions. No response carries the API key, a stack
trace or a provider message.

## Error kinds (changes)

| kind | HTTP | Fields | Meaning |
|---|---|---|---|
| `busy_task` | 409 | — | **replaces `busy_question`**: another question, summary or comparison is running (one model task at a time) |
| `invalid_request` | 422 | — | also: fewer than 2 or more than 4 papers, duplicates, no aspects, unknown aspect |
| `daily_limit` | 429 | `used`, `limit`, `resets_at`, `needed` | also when today's remaining requests are fewer than the run's plan (`needed`) |
| `not_saved` | 404 | — | no saved summary/comparison for this key |

## Summaries

### `GET /api/summaries`
`200 {"papers": [{"paper_id", "title", "arxiv_id", "summary": {"status": "current" | "stale" | "none", "created_at": str | null, "model": str | null}}], "plan": {"max_requests": 6}}`
— the Summarize tab's paper picker.

### `GET /api/summaries/{paper_id}`
`200 Summary` (data-model.md) with `status` `current` or `stale` (+ `stale_reason`), and
`"plan": {"max_requests": 6}` for a regeneration, and `pending` (`null`, or `{created_at, failed_parts,
retry_parts, verified_parts}` when a later regeneration ended with failed parts and this complete summary
was kept; posting `retry_parts` finishes it). `404 not_saved` (body also carries `plan`) |
`404 unknown_paper`. Never sends a model request.

### `POST /api/summaries/{paper_id}` (response: text/event-stream)
Body `{"regenerate": bool, "retry_parts": [str] | null}`. Before the stream: `422
invalid_request` (also for `retry_parts` on a stale summary, which only a full regeneration replaces), `404 unknown_paper`, `409 busy_task`, `429 daily_limit` (with `needed`).

| event | data |
|---|---|
| `plan` | `{"max_requests": 6, "parts": ["problem", …, "tldr"]}` |
| `progress` | `{"part": "method", "step": "searching" \| "reading" \| "generating" \| "checking", "passages"?: int}` |
| `retry_wait` | `{"part": "method", "attempt", "max_attempts", "wait_seconds", "reason"}` |
| `part` | a checked `Part` (only after its validation) |
| `summary` | the final `Summary` (saved) — last event |
| `error` | `{"kind": …}` — last event, only for failures outside any part (e.g. `internal`) |

A run stopped by a daily limit, long wait or busy model still ends with `summary` (its parts
show `not_started` with the reason).

## Comparisons

### `GET /api/comparisons?papers=a,b&aspects=method,datasets`
`200 Comparison` (current or stale) or `404 not_saved` (with `plan`). Order-insensitive.

### `POST /api/comparisons` (text/event-stream)
Body `{"paper_ids": [str] (2–4), "aspects": [str] (≥ 1), "regenerate": bool, "retry_aspects": [str] | null}`.
Same pre-stream errors and events as summaries, with `progress.part` = the aspect, `part` events
per cell (`part: "<aspect>:<paper_id>"`), and a `row_failed` event `{"aspect", "reason"}` for a
malformed row; ends with `comparison`.

## Changes to existing endpoints

- `POST /api/ask`: `409 busy_task` instead of `busy_question` (same meaning, now shared).
- `DELETE /api/papers/{id}` also removes that paper's saved results. Re-process jobs keep them, marked
  `stale` with `passages_changed`.
- A stale summary or comparison refuses `retry_parts` or `retry_aspects` with `422 invalid_request`.
