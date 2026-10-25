# ADR-0008: Per-Part Grounding and Structured Output

> **Scope**: Document decision clusters, not individual technology choices. Group related decisions that work together (e.g., "Frontend Stack" not separate ADRs for framework, styling, deployment).

- **Status:** Accepted (extends ADR-0004 from whole answers to parts)
- **Date:** 2026-10-25
- **Feature:** 004-summaries-comparison
- **Context:**
  - **New outputs with many claims:** Feature 4 adds summaries (a TL;DR and five sections) and
    comparison tables (2–4 papers × up to 5 aspects).
    - Each section and cell must be validated on its own, so one bad part doesn't hide the
      others (FR-011).
    - The TL;DR must carry citations and may only use what verified sections say (FR-005).
  - **ADR-0004 validates whole answers:** it checks citations against `1..n` for one answer.
    - Applied to a whole summary, a section could cite another section's passages and pass.
    - A second, summary-only validator would copy the grounding rules, and copies drift.
  - **Free models and tables:** they format markdown tables unreliably (pipes, line breaks,
    column alignment).
    - A table has to be located cell by cell before any cell can be validated.
  - **The answer validator has a known blind spot:** it checks citation numbers, not what the
    cited passage says.
    - A correct fact cited to the wrong passage passed it in Feature 2 (F1 in
      `eval/probe_notes.md`).
  - **Constraints:** Principle V (validation in code, not-found instead of guessing); Principle
    II (no new module without an amendment); one shared LLM boundary (`llm.generate`).

## Decision

- **One validator, scoped by an allowed set**:
  - `prompts.check_citations` and `service.review_reply` gain `allowed: set[int]`.
  - A part is validated only against the passage numbers that were given **for that part**.
    For a comparison cell, that means its own paper's passages in its row.
  - `ask()` keeps `allowed = {1..n}` and its behaviour; its tests stay unchanged.
  - The rules are ADR-0004's: invalid → held back with the unverified text viewable, none →
    not reported, uncited sentence → warning.
- **Shared building blocks**:
  - The `<passage>` block is factored out of `build_answer_prompt` as `format_passages` and used
    by answer, section and row prompts.
  - Passages are numbered once per run (`number_passages`), so a passage keeps one number
    wherever it is cited.
- **Part states**: `verified`, `not_reported`, `held_back`, `failed` (cut off, empty, malformed),
  `not_started` (run stopped).
  - No part's text is sent to the client before its check.
- **TL;DR checked in code** (`prompts.check_tldr`). The TL;DR is generated from the verified
  sections' text only, then:
  1. the not-found sentence → not reported;
  2. every sentence must cite;
  3. every citation must be one that a verified section cites;
  4. every number in a sentence must appear in the sections it cites.
  - A failure holds back the TL;DR alone; the sections stay shown.
  - With no verified section, the TL;DR is not reported and no request is made.
- **Comparison rows as JSON**:
  - One request per aspect.
  - The prompt asks for `{"cells": [{"paper": "P1", "text": "… [n]"}]}`.
  - `prompts.parse_row` strips code fences and surrounding text, then parses.
    - Malformed output → the row is `failed` (`malformed`) and retryable, never an exception
      past the orchestrator.
    - A missing cell → not reported. Extra cells and keys → ignored.
  - Each cell then goes through `review_reply` with its own allowed set.
  - No provider-specific JSON mode, so any OpenAI-compatible model works.
- **Output budget per part**: word limits (sections 80, TL;DR 60, cells 50) keep every call far
  below `MAX_OUTPUT_TOKENS` (2048, reasoning included).
  - A cut-off (`LLMError(reason="cut_off")`) fails that part only; truncated text is never
    stored or shown.

## Consequences

### Positive

- **Principle V in one place:** every generated part, from answers to table cells, is judged by
  the same code, so a fix to the rules applies everywhere.
- **Bad parts are contained:** a bad section or cell costs only that part. The rest of the
  summary or table stays usable, and a failed part can be retried for 1 request.
- **The TL;DR stays checkable:** it is checked without a second model call. Uncited sentences,
  citations outside the verified sections and invented numbers are caught deterministically,
  with a warning naming the broken rule.
- **JSON avoids table parsing:** cells are located without parsing markdown, and parse failures
  are a designed state rather than a crash.
- **Retries stay cheap:** small per-part outputs make cut-offs unlikely and retries cheap.

### Negative

- **The blind spot remains:** a non-numeric claim attached to a valid citation passes (the F1
  pattern). This holds for sections, cells and the TL;DR alike.
  - Detecting it needs the passage content and is assigned to the evaluation feature's
    faithfulness judge.
  - Until then: `docs/known-limitations.md` and the checkpoint 7 hand check.
- **Number-check false positives:** the TL;DR number check can reject a correct paraphrase
  ("10k" for "10,000"). Normalisation reduces this, but the TL;DR may be held back more often
  than needed.
- **Free-model JSON:** it may be malformed often enough to cost retries. The malformed rate is
  measured by checkpoint 7.
- **More requests:** per-part generation costs more than one request per summary (up to 6 per
  summary, 1 per aspect per comparison).

## Alternatives Considered

- **Whole-output validation** (one prompt for the full summary or table, checked against
  `1..n`):
  - one request;
  - but a part could cite another part's passages;
  - and one bad citation would reject the whole output, against FR-011.
  - Rejected.
- **A separate validator for summaries and tables:** the same rules in two places, which drift.
  Rejected.
- **Markdown tables with a table parser:** fragile with free models (pipes inside cells, missing
  rows, merged lines). Rejected.
- **Provider JSON mode (`response_format`):** stricter output, but not supported by every free
  model on OpenRouter, and it ties the engine to a provider feature (Principle III).
  - Kept as a later option inside `llm.py`; no contract changes would be needed.
- **TL;DR checks:**
  - **Generated from passages:** it could state what no verified section says. Rejected.
  - **Model-graded:** not code validation (Principle V). Rejected.
  - **Word-overlap similarity:** needs a threshold and can't be explained. Rejected.
  - **"Single section per sentence":** rejects the natural sentences that join a method and its
    result. Rejected.

## References

- Feature Spec: [specs/004-summaries-comparison/spec.md](../../specs/004-summaries-comparison/spec.md)
- Implementation Plan: [specs/004-summaries-comparison/plan.md](../../specs/004-summaries-comparison/plan.md)
- Research: R1 (one pipeline), R3 (TL;DR check and its blind spot), R4 (JSON rows), R5 (output
  budget) in [research.md](../../specs/004-summaries-comparison/research.md); part states in
  [data-model.md](../../specs/004-summaries-comparison/data-model.md)
- Related ADRs: ADR-0003 (LLM boundary and retries), ADR-0004 (grounding and citation
  validation)
- Evaluator Evidence: `eval/probe_notes.md` (F1, F2 faithfulness cases); checkpoint 7 results
  (to be recorded)
