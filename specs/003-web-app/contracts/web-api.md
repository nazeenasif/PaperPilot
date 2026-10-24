# Contract: PaperPilot Web API (Feature 3)

Base URL `http://127.0.0.1:8000` (bound to 127.0.0.1 only). JSON unless noted. CORS allows only
`FRONTEND_ORIGINS` (default `http://127.0.0.1:3000` and `http://localhost:3000`);
`TrustedHostMiddleware` accepts only `127.0.0.1` and `localhost` hosts. No authentication (local
single user; spec FR-002a). No response ever contains the API key, a stack trace or a provider
message.

**Cross-site request protection** (spec FR-002b, research R11). Both rules apply to every path,
before any endpoint runs:

1. A request whose `Origin` header is present and not one of `FRONTEND_ORIGINS` is refused with
   `403 {"kind": "forbidden", "reason": "origin"}`.
2. A `POST`, `PUT`, `PATCH` or `DELETE` without the header `X-PaperPilot: 1` is refused with
   `403 {"kind": "forbidden", "reason": "header"}`.

Requests without an `Origin` header (same-machine scripts) pass rule 1 but still need the header
to change state. The frontend sends `X-PaperPilot: 1` on every POST and DELETE, uploads
included.

## Errors

Every non-2xx response and every SSE `error` event has the body `{"kind": <kind>, ...fields}`.

| kind | HTTP | Fields | Meaning |
|---|---|---|---|
| `forbidden` | 403 | `reason` (`origin`, `header`) | foreign `Origin`, or a state-changing request without `X-PaperPilot: 1` |
| `not_ready` | 503 | `state` | model/library still loading or failed to load |
| `empty_question` | 422 | — | blank question |
| `no_papers_selected` | 422 | — | `paper_ids` given but empty |
| `unknown_paper` | 404 | `paper_id` | paper not in library |
| `unknown_passage` | 404 | `passage_id` | passage not in library |
| `pdf_missing` | 404 | `paper_id` | paper has no stored PDF |
| `not_found` | 404 | — | no such `/api` path |
| `invalid_request` | 422 | — | the request body or parameters failed validation |
| `busy_question` | 409 | — | another question is still being answered (FR-010) |
| `busy_job` | 409 | `paper_id` | a job for this paper is already queued or running |
| `daily_limit` | 429 | `used`, `limit`, `resets_at` | daily free requests used up (no model request made) |
| `rate_limited` | 429 | `until`, `daily` | provider asked for a wait > 60 s; `daily: true` → daily-limit screen |
| `model_busy` | 503 | `attempts` | all retries failed (429/5xx/timeouts) |
| `model_unavailable` | 502 | `reason` (`not_listed`, `unknown_model`, `bad_key`, `out_of_credits`, `cut_off`, `empty`) | configuration or model problem |
| `upload_invalid` | 400 | `reason` (`not_pdf`, `too_large`, `no_text`, `unreadable`, `password`) | rejected upload (also used inside jobs) |
| `internal` | 500 | — | unexpected; details only in server logs |

## Endpoints

### `GET /api/status`
`200 {"state": "loading" | "ready" | "error", "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
"model_is_free": true, "daily_limit": 50}` — always answers, even while loading.

### `GET /api/usage`
`200 {"used": 34, "limit": 50, "remaining": 16, "resets_at": "2026-10-25T00:00:00Z",
"source": "provider" | "local"}`. Refreshes from the provider at most every 30 s.

### `GET /api/papers`
`200 {"papers": [PaperCard], "total_passages": 223}`, sorted by title.

`PaperCard`: `{"paper_id", "title", "page_count", "passage_count", "text_passages",
"table_passages", "section_count", "arxiv_id": str | null, "has_pdf": bool,
"highlights": "exact" | "mismatch" | "no_pdf"}`.

### `POST /api/papers` (multipart/form-data, field `files`, one or more)
`202 {"jobs": [{"job_id", "file_name"}]}`. Size (≤ 25 MB, enforced while reading) and the
`%PDF-` signature are checked per file; a rejected file still gets a job that is immediately
`failed` with `upload_invalid`, so every dropped file has a row.

### `GET /api/jobs`
`200 {"jobs": [UploadJob]}` (see data-model.md). Snapshot for page load, reconnects and polling.

### `GET /api/jobs/events` (text/event-stream)
Events: `job` with an `UploadJob` payload on every change; keep-alive pings every 15 s. On
connect, the current snapshot of unfinished jobs is sent first.

A file whose content is already in the library without a stored PDF becomes an attach job:
phases `queued → mapping → ready`, outcome `pdf_attached`, `highlights` `exact` or `mismatch`
(no embedding; spec FR-018).

### `POST /api/papers/{paper_id}/reprocess`
`202 {"job_id", "file_name"}` — re-processes the paper from its stored PDF (parse, chunk, embed,
layout) as a `reprocess` job with the usual phases; passages are replaced only when the job
succeeds (FR-018a). `404 unknown_paper | pdf_missing`; `409 {"kind": "busy_job"}` if a job for
the same paper is already queued or running.

### `DELETE /api/papers/{paper_id}`
`200 {"removed_passages": 56}`; removes passages, PDF and layout. `404 unknown_paper`.

### `GET /api/papers/{paper_id}/pdf`
`200 application/pdf`, `Content-Disposition: inline`. `404 pdf_missing | unknown_paper`.

### `GET /api/passages/{passage_id}`
`200 PassageView`:
```json
{"passage_id": "a8ca46b17146-12", "paper_id": "a8ca46b17146", "title": "LoRA: …",
 "section": "Our Method", "page": 5, "page_count": 26, "kind": "text", "text": "…",
 "has_pdf": true,
 "layout": {"pages": [{"number": 5, "width": 612.0, "height": 792.0}],
            "regions": [{"page": 5, "x0": 108.0, "y0": 412.3, "x1": 504.1, "y1": 423.9}]},
 "layout_reason": null, "can_reprocess": false}
```
`layout` is `null` with `layout_reason` = `no_pdf` | `mismatch` | `unavailable` when the passage
cannot be marked; the viewer then shows the passage text beside the page (FR-013). For
`mismatch` (attached PDF whose regenerated passages did not match the stored ones),
`can_reprocess` is `true` and the viewer offers "Re-process paper for exact highlights", which
calls `POST /api/papers/{paper_id}/reprocess`. This endpoint never parses or builds layouts.

### `POST /api/search`
Body `{"query": str, "paper_ids": [str] | null, "k": int | null}` → `200 {"results":
[SearchResult]}` with `rank, score, passage_id, paper_id, title, section, page, text`. Makes no
model request ("Browse passages instead", FR-026).

### `POST /api/ask` (response: text/event-stream)
Body:
```json
{"question": "What are its limitations?", "paper_ids": ["a8ca46b17146"] | null, "k": null,
 "history": [{"role": "user", "text": "What is LoRA?"}, {"role": "assistant", "text": "…"}]}
```
Validation errors (`empty_question`, `no_papers_selected`, `unknown_paper`, `not_ready`) are
returned as a normal JSON error response before the stream starts. Only one question is
processed at a time; a second concurrent request gets `409 {"kind": "busy_question"}`.

Stream events (in order; `progress` and `retry_wait` may repeat):

| event | data |
|---|---|
| `progress` | `{"step": "rewriting" \| "searching" \| "reading" \| "generating" \| "checking", "passages": int?, "papers": int?}` |
| `retry_wait` | `{"attempt": 2, "max_attempts": 4, "wait_seconds": 8.0, "reason": "rate_limited" \| "timeout" \| "server_error" \| "provider_error"}` |
| `answer` | `Answer` (below) — the last event on success |
| `error` | `{"kind": …}` — the last event on failure (`daily_limit`, `rate_limited`, `model_busy`, `model_unavailable`, `internal`) |

`Answer` mirrors `service.Answer`:
```json
{"question": "…", "standalone_question": "…", "rewrite_applied": true,
 "rewrite_fallback_reason": null, "text": "… [1].", "not_found": false,
 "fallback_reason": null, "warning": null, "rejected_answer": null,
 "citations": {"valid": [1], "invalid": [], "uncited_sentences": []},
 "verified": true,
 "passages": [{"number": 1, "passage_id": "…", "paper_id": "…", "title": "…", "section": "…",
               "page": 5, "score": 0.712, "text": "…"}],
 "papers_read": 1, "word_count": 65, "llm_calls": 2,
 "requests": {"planned": 2, "retries": 0},
 "timings": {"rewrite": 3.3, "retrieve": 0.1, "generate": 14.0},
 "tokens": {"input": 2268, "output": 510, "reasoning": 506},
 "usage": {"used": 36, "limit": 50, "remaining": 14, "resets_at": "…", "source": "provider"}}
```
`verified` = `not not_found and citations.invalid == []` (spec FR-005). No `answer` text is sent
before the engine has checked citations (FR-011).

## Versioning
Unversioned paths under `/api` (one local client shipped from the same repository); breaking
changes are made in both halves in one commit.
