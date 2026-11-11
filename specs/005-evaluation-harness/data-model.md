# Data Model: Evaluation Harness (Feature 5)

## GoldenSet (`eval/golden.json`, committed)

| Field | Type | Notes |
|---|---|---|
| version | int | bumped by hand when a question changes meaning |
| questions | [GoldenQuestion] | 30–50 (FR-001) |

The file's SHA-256 is recorded with each result beside `version` (research R1).

## GoldenQuestion

| Field | Type | Notes |
|---|---|---|
| id | str | stable, e.g. `bert-02` |
| kind | `single` \| `cross` \| `near_miss` \| `off_topic` \| `follow_up` | |
| question | str | as a researcher would type it |
| scope | `library` \| `paper` | `library`: the 5 golden papers; `paper`: filtered to `papers[0]` |
| papers | [arXiv ID] | 1 for single and paper-scoped, ≥ 2 for cross; empty for off-topic |
| expected | str | the answer in one sentence, or `"not_found"` |
| evidence | [Evidence] | ≥ 1 when answerable; none for not-found |
| turns | [{role, text}] | follow-up only: the earlier turns |
| standalone | str | follow-up only: used by retrieval-only runs (FR-003) |
| known_case | `F1` \| `F2` \| `Q2` \| `Q4` \| null | FR-005 |
| note | str \| null | |

Validation (research R2): composition per FR-001; every evidence phrase matches a stored passage of its
paper and is on its stated page; no field holds a passage ID; arXiv IDs resolve to library papers.

## Evidence

`{paper: arXiv ID, page: int (1-based), phrase: str}`, a phrase copied from the paper, short enough to
fall within one passage.

## Experiment (`eval/experiments.json`, committed)

| Field | Type | Notes |
|---|---|---|
| name | str | `baseline`, `rerank-minilm-l6`, `rerank-tinybert`, `hybrid-rrf60`, `prefix`, `reasoning-low`, `gemma`, `scope-rule-off` |
| changes | {setting: value} | empty for the baseline, exactly one entry otherwise (FR-023) |
| answers | bool | whether answer evaluation is run for it (baseline, and the best retrieval row, FR-024a/b) |
| optional | bool | reasoning effort, the second model and the scope rule (FR-024a) |
| set | `golden` \| `scope_set` | the scope-rule rows run on the fixed set (FR-025) |
| runs | int | 1, or ≥ 3 per condition for the scope rule (FR-025) |
| takeaway | str \| null | written by the developer; required for acceptance (US5 scenario 3) |

## Configuration (stored with every result)

`answer_model`, `judge_model`, `reasoning_effort`, `output_tokens`, `instruction_hashes` (answer,
rewrite, section, TL;DR, row, judge), `summary_prompt_version`, `judge_prompt_version`, `chunk_words`,
`chunk_overlap`, `min_chunk_words`, `embed_model`, `embed_prefix`, `retrieval`
(`{method: vector | rerank | hybrid, k, shortlist, reranker, revision, rrf_k, bm25: {k1, b}}`),
`relevance_threshold`, `scope_rule`, `paper_fingerprints`, `golden: {version, sha256}`, `commit`.
Derived (ignored by the one-variable check): `paper_fingerprints`, `commit`.

## RunProgress (cache, `data/eval/eval.sqlite3`)

| Field | Notes |
|---|---|
| experiment, stage | stage: `retrieval`, `answers`, `judge`, `calibration`, `scope` |
| planned, done, requests {planned, retries} | updated after each unit |
| sessions | [{started_at, slice, used, ended_by: done \| slice \| daily_limit \| rate_limited \| busy}] |

States: `not_started → in_progress → done`; `in_progress` survives across days (FR-019).

## StoredAnswer (cache)

Key: configuration hash (answer-relevant fields only) + question id + run index. Value: answer text,
`not_found`, citation report, numbered passages (text snapshot), timings, requests, tokens, created_at.

## ClaimVerdict (cache)

Key: SHA-256(claim text, cited passage texts in order, judge model, judge prompt version, mode). Value:
claim, passages, verdict (`supported` | `partly` | `unsupported` | `not_judged`), reason, judge
requests, tokens, created_at. `not_judged` is never cached as final: a later run retries it.

## CalibrationItem (`eval/calibration.json`, committed)

`{id, source: "docs/verification/<report>#<claim n>" | "eval/probe_notes.md#F2-4", claim, passages:
[{paper, section, page, text}], hand_verdict: supported | partly | unsupported, note}`

## ResultRow (`eval/results/<experiment>.json`, committed, no paper text)

`{experiment, configuration, measured_at, retrieval: {hit@1, hit@3, hit@6, hit@10, mrr, per_kind,
gated_not_found, latency_s}, answers: null | {faithfulness, counts {supported, partly, unsupported,
uncited, not_judged}, correct_refusals, false_not_found, citation_valid, latency_s, per_kind},
requests {planned, retries}, self_graded: bool, runs: [per-run F2-type counts] (scope rule only),
questions: [{id, rank, outcome, verdicts summary}]}`

A row whose golden version or hash differs from the current file is shown as measured on an earlier set.
