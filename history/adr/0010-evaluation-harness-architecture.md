# ADR-0010: Evaluation Harness Architecture

> **Scope**: Document decision clusters, not individual technology choices. Group related decisions that work together (e.g., "Frontend Stack" not separate ADRs for framework, styling, deployment).

- **Status:** Proposed
- **Date:** 2026-11-11
- **Feature:** 005-evaluation-harness
- **Context:**
  - **What the harness must do**: measure retrieval and answers against a golden set, for configurations
    PaperPilot does not ship (a cross-encoder, BM25 fusion, a prefixed embedding, a second model, the
    scope rule off), through the real answer pipeline (FR-009).
  - **What it must not do**:
    - change the researcher's library, saved results or defaults (FR-008, FR-026, SC-009);
    - add user-facing features (FR-030);
    - spend the daily budget unannounced (FR-017–FR-019).
  - **Principle II** fixes the engine's module list (`config`, `errors`, `ingest`, `store`, `library`,
    `prompts`, `llm`, `service`) and allows only `llm.py` to talk to a model.
  - **Size**: about 1,000 lines with ten responsibilities (golden set, metrics, fusion, reranking, prefix
    library, claims, judge, calibration, sessions, report), well beyond a checkpoint script.

## Decision

- **A sibling package `evaluation/`**, run as `python -m evaluation <command>` (contracts/cli.md). It
  imports `paperpilot` and is never imported by it, the API or the frontend, like the API adapter.
  Its modules are `golden`, `retrieval`, `libraries`, `answers`, `judge`, `calibration`, `runs`,
  `store`, `experiments` and `report`.
- **Engine seams, each defaulting to today's behaviour**:
  - `service.ask(..., retrieve=None)`: a function returning passages and the gate score;
  - `llm.generate(..., model=None)` and a task kind `judge`;
  - `service.summarize/compare(..., save=False)`;
  - settings `USAGE_DIR`, `EMBED_PREFIX`, `SCOPE_RULE`, `EVAL_JUDGE_MODEL` and `EVAL_RESERVE`, read
    through `config`.
- **Experimental code stays in the harness**: rerankers, BM25 fusion and the judge prompt live in
  `evaluation/` until a later change adopts a result into the engine.
- **Isolation by settings**: an experiment applies its one change through settings for its own run.
  The prefix experiment uses a separate `LIBRARY_DIR` (`data/eval/libraries/prefix/`), with
  `USAGE_DIR` pointing at the main counter.
- **Storage split**:
  - committed and free of paper text: `eval/golden.json`, `eval/experiments.json`,
    `eval/calibration.json`, `eval/results/*.json`;
  - gitignored, holding passage text: `data/eval/eval.sqlite3` (answers, verdicts, progress).
  - The README table is generated from the committed files only.
- **Work in units, sessions in slices**: an answer, a judge request or a summary part is one unit and
  cached once done. A session takes a slice of today's quota, keeps a reserve (default 10) and resumes
  on any later day (research R10).

## Consequences

### Positive

- **The product stays as it is**: no experimental retrieval or judge code ships in the engine, and every
  seam's default reproduces today's behaviour, so existing tests keep their meaning.
- **Real pipeline, real numbers**: answers come from `service.ask` itself, not a copy of it, so results
  measure what researchers use.
- **Single LLM boundary kept**: the judge goes through `llm.generate`, with its retries, output limits
  and the shared request counter.
- **Reproducible rows**: committed results with the full configuration regenerate the README table on a
  fresh clone, without the cache or the PDFs.
- **Fits the free tier**: retrieval experiments cost nothing; answer runs spread over days without
  repeating work or spending the reserve.

### Negative

- **A second package**: an exception to Principle II's module list, recorded in the plan's Complexity
  Tracking; contributors must know that `evaluation/` is not product code.
- **Seams widen the engine's surface**: four optional arguments and five settings that the product never
  sets; each needs a test that its default changes nothing.
- **Adopting a result is a second step**: a winning reranker must be moved into the engine later, with
  its own tests, rather than switched on.
- **The cache is local**: answers and verdicts live in a gitignored file; a fresh clone can regenerate
  the report but not re-judge without spending requests.

## Alternatives Considered

- **Scripts in `scripts/`, as for the checkpoints**: no shared, importable, unit-testable modules for
  about 1,000 lines; rejected.
- **New modules inside `paperpilot`** (for example `paperpilot/evaluate.py`, `paperpilot/hybrid.py`):
  breaks Principle II's module list and ships experimental code with the product; rejected.
- **A copy of the answer pipeline inside the harness**: no seams needed, but it would drift from
  `service.ask` and measure something researchers do not use; rejected.
- **RAGAS or another evaluation framework**: out of scope in the spec, and it would hide the metrics'
  definitions behind a dependency; rejected.
- **Separate Chroma collections in the main library directory for experiments**: one step from the
  real library, and the store caches its client per directory; rejected for a separate `LIBRARY_DIR`.

## References

- Feature Spec: [specs/005-evaluation-harness/spec.md](../../specs/005-evaluation-harness/spec.md)
- Implementation Plan: [specs/005-evaluation-harness/plan.md](../../specs/005-evaluation-harness/plan.md) (Structure Decision, Complexity Tracking)
- Research: R1, R6, R10, R11 and R12 in [research.md](../../specs/005-evaluation-harness/research.md);
  [data-model.md](../../specs/005-evaluation-harness/data-model.md);
  [contracts/cli.md](../../specs/005-evaluation-harness/contracts/cli.md) and
  [contracts/engine-api.md](../../specs/005-evaluation-harness/contracts/engine-api.md)
- Related ADRs: ADR-0003 (LLM boundary, extended by `model`), ADR-0007 (request accounting, shared via
  `USAGE_DIR`), ADR-0009 (saved results, protected by `save=False`)
- Evaluator Evidence: Checkpoint 11 (to be recorded)
