# Research: Paper Summaries and Cross-Paper Comparison (Feature 4)

Decisions behind `plan.md`. Each entry: **Decision**, **Rationale**, **Alternatives considered**.
Facts about the existing engine were checked in the code on 2026-10-25 (`paperpilot/service.py`,
`prompts.py`, `llm.py`, `library.py`).

## R1. One grounding pipeline, extended rather than copied

**Decision**: summaries and comparisons are built from the same pieces `ask()` uses, and those
pieces are generalised in place:

| Piece (existing) | Reused for | Change |
|---|---|---|
| `library.search(query, k, paper_ids)` | every facet and every (paper, aspect) retrieval | none |
| `service._number` | numbering passages | generalised to `number_passages(results, start, seen)`: keeps one number per passage id across a run (FR-004) |
| `prompts.strip_reference_markers`, `_escape`, the `<passage>` tag format | every prompt | the passage block of `build_answer_prompt` is factored out as `format_passages(passages)` and shared |
| `prompts.extract_citations`, `_sentences`, `is_not_found` | every part | none |
| `prompts.check_citations(text, passage_count)` | every part | gains `allowed: set[int]`; `passage_count` becomes the special case `allowed = {1..n}` |
| `service.review_reply(text, passage_count)` | every summary section and comparison cell | gains `allowed`; returns the same `(text, citations, warning, rejected, fallback_reason)` tuple |
| `llm.generate` (retries, `RetryNotice`, daily pre-check, long-wait rule, `cut_off`/`empty` reasons, shared counter) | every model call | none |
| `on_event` progress callback and `api/streams.run_streaming` | progress per part | events gain a `part` field |

`ask()` keeps its behaviour exactly; its tests stay green unchanged, which proves the
refactor is behaviour-preserving.

**Rationale**: Principle V lives in one place. A section that cites a number outside its own
passages is judged by the same function that judges answers, with the same not-found, held-back
and uncited-sentence rules.

**Alternatives considered**: a separate `summaries` validator (rejected: a second copy of the
rules would drift); validating against `1..n` for the whole summary (rejected: a section could
then cite another section's passages and still pass).

## R2. Summary facets, queries and sizes

**Decision**: five fixed facets, each with a retrieval query and an instruction in `prompts.py`:

| Facet | Retrieval query (embedded) | What the section must state |
|---|---|---|
| problem | "the problem, motivation and research question addressed by this paper" | the problem and why it matters |
| method | "the proposed method, model architecture and how it works" | the approach |
| data | "datasets, corpora, benchmarks and experimental setup used" | data and benchmarks |
| results | "main results, performance compared with baselines, key numbers" | main findings with numbers copied exactly |
| limitations | "limitations, weaknesses, failure cases and future work" | stated limitations only |

Each facet retrieves **4 passages** from the one paper (`paper_ids=[paper_id]`, spec
Assumptions). The relevance threshold gates a facet as it gates a question: if the best passage
scores below `RELEVANCE_THRESHOLD`, the section is **not reported** and **no request is made**.
A section is at most 80 words.

**Rationale**: query-focused retrieval keeps each prompt small (4 × ~220 words) and each claim
next to its passages. The threshold was calibrated on questions (Feature 2 research R8), not on
these fixed facet queries, so it was measured for them (analysis finding C1, 2026-10-25, 0 model
requests): top score per facet within each paper, k = 4.

| Paper | problem | method | data | results | limitations |
|---|---|---|---|---|---|
| Attention Is All You Need | 0.699 | 0.703 | 0.752 | 0.713 | 0.584 |
| BERT | 0.644 | 0.724 | 0.745 | 0.697 | 0.601 |
| LoRA | 0.642 | 0.715 | 0.736 | 0.707 | 0.608 |
| Lost in the Middle | 0.695 | 0.722 | 0.734 | 0.731 | 0.639 |
| RAG | 0.698 | 0.707 | 0.747 | 0.709 | 0.634 |

Every facet clears 0.58 on the five test papers, so the gate does not suppress sections here.
Limitations is the weakest facet (0.584–0.639; Attention is 0.004 above the gate): a paper whose
limitations are phrased differently may be reported as not found without a request. Re-measure
when the facet queries, papers or threshold change.

**Which sections a facet searches** (added 2026-11-04, one change at a time, each followed by
`scripts/probe_facets.py`; results in `eval/facet_probe.md`). The rules live in one table,
`prompts.FACETS` (query, preferred sections, exclusions), which comparison aspects are to share:

- **No facet searches Related Work or Front Matter.** Related Work describes other papers' work, so
  citing it in this paper's summary is a faithfulness hazard that citation checks cannot catch: the
  citation is valid, the passage really says it, and the claim is still not about this paper. Front
  Matter holds titles and authors. Sections are matched by name, ignoring case, so "Related Works"
  counts. A paper with nothing else (no detected headings) searches them anyway rather than report
  nothing. Questions are not filtered: someone can ask what a paper says about earlier work.
- **Problem reads the Abstract and Introduction first**, which is where a paper states its problem, and
  tops up to 4 from the whole-paper search if they hold fewer; a paper with neither reads 4 from the
  whole-paper search.
- **Limitations reads up to 2 passages from sections named Limitations, Discussion or Conclusion, and
  fills the rest from a whole-paper search** (Related Work and Front Matter still excluded), so it
  reads 4 as the spec says, unless the paper has fewer. Papers often state limitations outside such a
  section, so it is not restricted to them. A paper with no such section reads 4 from the whole-paper
  search.
- **The relevance gate judges a whole-paper search; the preferred sections only choose what is read.**
  The gate answers "does this paper cover the facet?", the restriction answers "where to read it".
  They are separate because restricting a search lowers its top score, while the threshold was
  calibrated on unrestricted searches: LoRA's Problem scored 0.573 in its Introduction (under 0.58)
  and 0.642 across the paper, and its Introduction does state the problem. The whole-paper search
  still leaves out Related Work and Front Matter. A wrong pass fails safe: the model is told to reply
  "Not reported" when the passages do not cover the topic (`SECTION_INSTRUCTION` rule 6). That reply
  is an instruction the model follows, not something the code enforces, and a wrong pass costs one
  request.

**Alternatives considered**: using `TOP_K` (6) per facet (rejected per clarification: larger
prompts for little gain); one retrieval for the whole paper (rejected: the "data" and
"limitations" passages rarely rank for a generic query).

## R3. The TL;DR and how it is checked

**Decision**: the TL;DR is generated **after** the five sections, from the **text of the
verified sections only** (with their citation numbers), not from passages. It is checked by a
pure function `prompts.check_tldr(text, sections)` in four steps; any failure holds the TL;DR
back, while the sections stay visible:

1. **Not found**: if the reply is the not-found sentence, the TL;DR is *not reported*.
2. **Every sentence cites**: the reply is split with the same sentence splitter as answers
   (`_sentences`); a sentence without a citation fails the check (stricter than answers, where
   an uncited sentence is only a warning — the TL;DR must not add uncited claims).
3. **Citations are a subset**: let `U` be the union of the valid citations of the verified
   sections. Every number cited in the TL;DR must be in `U`; a number outside `U` (including a
   valid passage number that only a held-back section cited) fails the check.
4. **Each sentence is traceable**: for each sentence `s` with citations `C(s)`, its *sources*
   are the verified sections whose citations intersect `C(s)` (non-empty after step 3). Every
   number written in `s` (digits, with `,`/`.`/`%`/`×` normalised) must appear in the text of
   one of its sources. A sentence whose number does not appear in its sources fails the check.

The result records each sentence's sources (e.g. "Problem, Results"), so tests and the
checkpoint can show where every TL;DR sentence came from.

**On failure**: the TL;DR part becomes *held back*, with a warning naming the failing check
("sentence 2 cites passage 9, which no verified section cites"; "sentence 1 states 10,000,
which its sources do not contain"), the rejected text viewable as unverified, and **all
sections still shown**. If **no** section is verified, the TL;DR is *not reported* and **no
request is made** (spec US4 scenario 5).

**Rationale**: steps 2–3 make the spec's "citations are a subset of the sections' citations"
mechanical; step 4 makes "traceable to a section" checkable in code without a second model
call. Numbers are where summaries invent most often (a wrong "10,000×" reads as authoritative),
and a number check is deterministic and cheap. The TL;DR is short (≤ 60 words, ≤ 3 sentences),
so the rule is strict without rejecting normal output.

**Alternatives considered**: requiring each sentence's citations to come from a single section
(rejected: a natural TL;DR sentence joins two sections, e.g. method and result); word-overlap
similarity between sentence and section (rejected: needs a threshold and is unexplainable);
asking the model to check its own TL;DR (rejected: model-graded checks are not code
validation, Principle V); generating the TL;DR from passages (rejected: it could then state
things no verified section says).

**What it was built from** (added 2026-11-04): the TL;DR part records `built_from`, the sections
whose text it used, and `built_without`, the sections it went without (failed, held back, or
regenerated since). Regenerating a section costs 1 request and does not rewrite the TL;DR, whose
text still reflects the old section, so it reads "Built without <section>" and the badge "All
citations verified" is withheld until the TL;DR is regenerated too (1 request). A section the paper
does not report is not listed: there was nothing to use. Summaries saved before this was recorded
take these values from their section states, since no section could have been retried by then.

**What the check catches, and what it cannot**: it catches (a) a TL;DR sentence with no
citation, (b) a citation to a passage that no verified section cites, and (c) a number that
does not appear in the sections the sentence cites. It **cannot** catch a non-numeric claim
attached to a valid citation — a sentence whose citations all belong to verified sections and
whose wording contains no number, but which says something those sections (or the cited
passages) do not support. This is the **F1 pattern** recorded in `eval/probe_notes.md` (a correct
fact cited to the wrong passage, "Wq and Wv" cited to [2] while only [1] says it), which passed
answer validation in Feature 2; the same holds for the sections and comparison cells, which use
the same validator. Detecting it requires checking what each cited passage says, which is
assigned to the evaluation feature's **faithfulness judge**; until then the limitation is
recorded in `docs/known-limitations.md` and claims are checked by hand in checkpoint 7.

**Scope rule (added 2026-11-05; a hypothesis, not a measured fix).** The section and TL;DR instructions
now say: "Keep every claim's scope exactly as its source passage states it (models, datasets,
conditions); never extend a result to models or tasks the passage does not name." It comes from F2
(`eval/probe_notes.md`), which has 4 recorded occurrences: a result stated for one model or task,
extended to others while combining sources. Validation cannot see this, because the citations are valid
and the numbers appear in the passages. Whether the rule reduces F2 is to be measured in the evaluation
feature: one regenerated summary shows nothing either way. Comparison cells take the same rule when
they are built (T016).

## R4. Comparison rows as structured JSON

**Decision**: one request per aspect (clarification). For aspect `a`, each paper `p` gets its
own retrieval of **3 passages** (`paper_ids=[p]`, query from the aspect's fixed query). Passages
are de-duplicated by passage id and numbered once per comparison (a passage seen in an earlier
row keeps its number). The prompt groups passages by paper under labels `P1…P4` and asks for
**JSON only**:

```json
{"cells": [{"paper": "P1", "text": "... [3]."}, {"paper": "P2", "text": "Not reported in the retrieved passages."}]}
```

`prompts.parse_row(reply, labels)` is tolerant and never raises past its caller: it strips code
fences, takes the outermost `{…}` if text surrounds it, and `json.loads` it. Outcomes:

- **Malformed** (no JSON object, invalid JSON, `cells` not a list): the **row fails** with
  reason `malformed`; it can be retried on its own (1 request). Never a crash.
- **Per cell**: a missing cell or an unknown label → that cell *not reported*; extra cells and
  extra keys are ignored and never shown; a non-string `text` → *not reported*.
- **Validation**: each cell's text goes through `review_reply(text, allowed=numbers of that
  paper's passages in this row)`; a citation to another paper's passage is invalid for that cell
  (FR-010). The exact sentence `NOT_REPORTED` (or the not-found sentence) → *not reported*.

A paper whose best passage for the aspect is below the threshold is still sent with no passages
listed and the instruction that its cell must read `NOT_REPORTED`; if **every** paper is below
the threshold the row is *not reported* without a request.

**Rationale**: JSON gives one object per cell, so each cell is located and validated without
parsing a markdown table (whose pipes, line breaks and alignment free models get wrong).
Per-paper retrieval with equal `k` stops a long paper from crowding out a short one (FR-008).

**Alternatives considered**: a markdown table (rejected: brittle parsing, cells with `|` break
it); provider JSON mode (`response_format`) (rejected for now: not supported by every free model
on OpenRouter; the tolerant parser works with any model and can be combined with JSON mode later
without contract changes); one retrieval across all selected papers (rejected: FR-008).

## R5. Output budget and cut-off

**Decision** (amended 2026-11-04 after the measurement below): the output limit is set per task
kind in `llm.OUTPUT_TOKENS`, passed as `llm.generate(..., task=...)`:

| Task kind | `max_tokens` | Requested length | Note |
|---|---|---|---|
| `answer` | 2048 | ≤ 150 words | unchanged, so `ask()` behaves as before |
| `summary_section` | 4096 | ≤ 80 words | |
| `tldr` | 4096 | ≤ 60 words, ≤ 3 sentences | |
| `comparison` | 4096 | ≤ 50 words per cell | one call writes a row of up to four cells |

Reasoning effort stays as configured; that experiment belongs to the evaluation feature.
OpenRouter's model list (2026-11-04) gives `nvidia/nemotron-3-ultra-550b-a55b:free` a
`max_completion_tokens` of 65,536, so 4096 is well within it. **4096 is not yet verified by a real
run.** The call that hit the old limit (Method) was cut off, so its true need is unknown, and a
comparison row has not been measured at all.

A `finish_reason == "length"` already raises `LLMError(reason="cut_off")` in `llm.generate`; the
orchestrator catches it **per part**, marks that part *failed (cut_off)* and continues. Truncated
text is never stored or shown. The checkpoint prints input, output and reasoning tokens per part
so the headroom is measured, not assumed.

**Rationale**: the existing boundary already distinguishes cut-off from other failures; only the
handling changes from "fail the answer" to "fail this part".

**Alternatives considered**: keeping 2048 with word limits, as first decided (rejected by the
measurement below: word limits do not control reasoning); `LLM_REASONING_EFFORT=low` (not taken
here: it could change faithfulness, so it stays an evaluation-feature experiment); raising the
limit for every call (rejected: answers have no measured need, and a higher limit lets runaway
reasoning take longer); summarising in one long call (rejected: the most likely way to be cut off).

**Measured 2026-11-04 (checkpoint 7, LoRA summary): the first decision's headroom was wrong.** It
assumed 220-510 reasoning tokens from Feature 2 and 3 answers and over 1,100 tokens to spare. The
provider's output count includes reasoning. Reasoning was 943-1,679 tokens per summary part, about
three times the assumption, while visible text was only 75-246 tokens. Output used:

| Part | Output of 2,048 | Reasoning | Visible |
|---|---|---|---|
| Limitations | 1,018 | 943 | 75 |
| Problem | 1,301 | 1,184 | 117 |
| Data | 1,473 | 1,317 | 156 |
| TL;DR | 1,790 | 1,665 | 125 |
| Results | 1,925 | 1,679 | 246 |
| Method | cut off at the cap | unknown | none |

Word limits do not create headroom on this model, because reasoning dominates. The per-part
failure handling worked as designed (no truncated text; the other parts stayed), but one part in
six being cut off is too often, which led to the per-task limits above.

## R6. Saved results: SQLite cache, keys and invalidation

**Decision**: a SQLite file `<LIBRARY_DIR>/results.sqlite3` (WAL, `BEGIN IMMEDIATE` writes, as
`usage.sqlite3`) with one table:

| column | meaning |
|---|---|
| `kind` | `summary` or `comparison` |
| `key` | SHA-256 of the canonical key (below) |
| `paper_ids` | comma-separated, sorted (for invalidation by paper) |
| `result` | the run's JSON (parts, passages, requests, tokens) |
| `model`, `prompt_version`, `created_at` | shown to the researcher (FR-018) |

Canonical key: `kind`, the sorted paper content IDs, each paper's **passage fingerprint**
(SHA-256 of its stored passage ids and texts, in order), the sorted aspects (comparisons), the
**prompt version** (`prompts.SUMMARY_PROMPT_VERSION`, raised whenever facet queries,
instructions or the TL;DR rule change) and `LLM_MODEL`.

Invalidation is double:

1. **Explicitly**: `library.delete_paper` and `library.reprocess_paper` call
   `library.forget_results(paper_id)`, deleting every row that includes the paper. (The paper ID
   is the hash of the PDF bytes, so re-processing the same PDF keeps the same ID — the key alone
   would not change when only the chunk settings did.)
2. **By key**: a lookup recomputes the fingerprint, version and model; a row saved under another
   model or version is returned as **stale** with its reason (`model_changed`,
   `instructions_changed`, `passages_changed`), readable but never shown as current (FR-017).

Parts are saved as they finish (FR-020): a run's row is written when the run ends, including
failed parts; a part retry rewrites the row. A regeneration writes to a **new** row and replaces
the old one only on completion (FR-019).

**Rationale**: SQLite is in the standard library, already used for usage counts, safe for the
API and scripts at once, and survives restarts. Explicit invalidation is exact; key comparison
catches what explicit hooks cannot (a model change in `.env`).

**Alternatives considered**: JSON files per result (rejected: no atomic replace across
processes without extra locking); storing summaries in ChromaDB metadata (rejected: wrong tool,
re-embedding coupling); keying by passage ids only (rejected: misses model and instruction
changes).

## R7. Module placement under Principle II

**Decision**: no new module.

- `prompts.py`: facet and aspect queries and instructions, `SUMMARY_PROMPT_VERSION`,
  `NOT_REPORTED`, `format_passages`, `build_section_prompt`, `build_tldr_prompt`,
  `build_row_prompt`, `parse_row`, `check_tldr` (all pure).
- `service.py`: `summarize()`, `compare()`, the request plan and per-part orchestration, next to
  `ask()`.
- `library.py`: the results cache (`save_result`, `load_result`, `forget_results`) — saved
  results are per-paper library data, deleted with the paper.
- `llm.py`: unchanged.

**Rationale**: the constitution fixes the module list; each addition matches an existing
module's responsibility. `service.py` grows from ~210 to ~550 lines, which stays readable.

**Alternatives considered**: a new `summaries.py` module (rejected: needs a constitution
amendment for a split that is not yet needed — revisit if `service.py` passes ~700 lines);
caching in the API layer (rejected: scripts and the checkpoint must reuse saved results too,
and the API must stay a thin adapter).

## R8. Run control: plan, limits, failures, one task at a time

**Decision**:

- **Plan**: a summary's maximum is `5 + 1 = 6` requests; a comparison's is the number of
  aspects; a retry's is the number of parts retried (the TL;DR is its own part, R3). The
  plan is known before any request and returned with every saved result and every run.
- **Pre-check**: `service` refuses a run when `llm.usage().remaining < plan` by raising
  `DailyLimitError` before any request (FR-023); the API maps it to the existing `daily_limit`
  kind before the stream starts.
- **Per-part failures**: `cut_off`, `empty`, `malformed` → that part *failed*, the run continues.
  `DailyLimitError`, `RateLimitedError`, `model_busy` (all retries spent) and `model_unavailable`
  → the run **stops**: finished parts are kept and saved, the remaining parts are *not started*
  with the same reason, and no further request is sent (FR-024). Stopping on `model_busy` avoids
  spending up to 4 attempts on each remaining part while the provider is overloaded.
- **Accounting**: first attempts never exceed the plan (each part makes at most one
  `llm.generate` call); retries are reported separately from `llm.request_counts()`.
- **One task at a time**: the API's `question_lock` becomes a `model_lock` shared by `/api/ask`,
  summaries and comparisons; a refused start returns the new kind `busy_task` (which replaces
  `busy_question`; frontend copy: "PaperPilot is still working on another answer, summary or
  comparison").

**Rationale**: the free tier's ~50 requests a day make the plan the user's main decision input;
stopping on systemic failures protects it.

## R9. Progress and part events

**Decision**: the engine's `on_event(kind, detail)` gains part-level events:
`plan` ({max_requests, parts}), `progress` ({part, step: searching|reading|generating|checking,
passages?}), `retry_wait` ({part, …}), and `part` (the checked part, sent **after** its
validation). The API forwards them as SSE through `run_streaming`, ending with `summary` or
`comparison` (the saved result) or `error`. No event carries unchecked model text (FR-012).

## R10. Rejected alternative: map-reduce summaries (FR-006)

Summarising every passage ("map") then combining the partial summaries ("reduce") costs one
request per passage plus reduce steps: LoRA (56 passages) would need ~60 requests, more than a
day's free allowance for one paper. It also detaches statements from passages: after the reduce
step, a sentence summarises summaries, and its citations can no longer be checked against the
text that supports it. Query-focused retrieval per facet costs 6 requests per paper, keeps every
statement next to ≤ 4 citable passages and reuses the answer validator unchanged.

## R11. Checkpoint 7 plan

`scripts/checkpoint_7_summaries.py` runs against the running API (like checkpoint 6), checks
`scripts/usage.py` first, and prints its plan before sending anything:

| Part | Requests (max) |
|---|---|
| `summary`: LoRA summary (regenerate, so it is real) | 6 |
| `reopen`: GET the LoRA summary, usage unchanged | 0 |
| `compare`: BERT vs RAG on Method, Datasets, Results | 3 |
| `not-reported`: BERT vs RAG on Limitations (BERT states none) | 1 |
| `states`: scripted per-part failures in-process (held back, not reported, cut off, malformed, TL;DR rejected) | 0 |
| **Total** | **10** (cap 20 with retries) |

It prints every claim — each sentence of each part — with its citation numbers and, for each
number, the paper, section, page and the first 200 characters of the passage, and writes the
same list to `docs/verification/checkpoint-7-<date>.md` with empty **Verdict** and **Fault
(retrieval / model)** columns for the hand check (FR-027, SC-002).

The `not-reported` part asserts at least one *not reported* cell; if the model does report a
BERT limitation from its passages, the part prints the cell and its citations and records INFO
instead of failing, and the offline `states` part still demonstrates the state (SC-004).
