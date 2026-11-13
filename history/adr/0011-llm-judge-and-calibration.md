# ADR-0011: LLM Judge and Calibration

> **Scope**: Document decision clusters, not individual technology choices. Group related decisions that work together (e.g., "Frontend Stack" not separate ADRs for framework, styling, deployment).

- **Status:** Proposed
- **Date:** 2026-11-11
- **Feature:** 005-evaluation-harness
- **Context:**
  - **Citation checks cannot see faithfulness**: a valid citation can carry a claim the passage does
    not make. `eval/probe_notes.md` records three patterns that all passed validation:
    - F1, a correct fact cited to the wrong passage;
    - F2, scope extended to other models or tasks (at least 4 times);
    - F3, a real number placed against the wrong item (3 runs).
  - **The spec requires a judge** that sees only a claim and its cited passages, gives supported,
    partly or unsupported with a reason (FR-012), avoids self-grading (FR-013) and never counts an
    unreadable verdict as supported (FR-014).
  - **A judge must earn trust**: the recorded cases are all failures, so a judge that always said
    "unsupported" would agree with every one of them (FR-022).
  - **Budget**: about 50 free requests a day, so the judge's cost and its cache matter as much as its
    accuracy.

## Decision

- **Model**:
  - `google/gemma-4-31b-it:free` judges while `nvidia/nemotron-3-ultra-550b-a55b:free` answers, and the
    other way round for the second-model row.
  - Both were verified on OpenRouter's free list on 2026-11-11.
  - Set by `EVAL_JUDGE_MODEL`, called through `llm.generate(model=...)` with task kind `judge`
    (8,192 output tokens, reasoning included).
  - A row whose judge is its answerer is marked self-graded.
- **Input**:
  - Claims are the sentences found by the validator's sentence rule, each with only the passages it cites
    in `<passage>` tags as data. No question, expected answer, other claims' passages or answering model.
  - Uncited sentences are not judged and count against faithfulness.
- **Rules given to the judge**:
  - Judge only against the passages, never outside knowledge.
  - *Supported*: every part is stated or directly implied.
  - *Partly*: some part is, but another is not. This includes a wider scope than the passage's, and a
    number given to a different item.
  - *Unsupported*: the passages do not say it.
- **Output**: JSON `{"verdicts": [{"claim", "verdict", "reason"}]}`, parsed tolerantly. An unreadable,
  missing or cut-off verdict is **not judged**, never supported, and is retried on a later run.
- **Granularity**:
  - calibration makes one request per claim;
  - experiments make one request per answer, summary part or comparison row, with each claim beside
    its own passages.
- **Cache key**: SHA-256 of the claim, its passages' texts in order, the judge model,
  `JUDGE_PROMPT_VERSION` and the mode (single or batch).
- **Calibration**:
  - Items are stored in `eval/calibration.json` with a snapshot of their passages' text. They come from
    the verification reports' Verdict column (`correct`, `partly` and `wrong` mapped to the three labels)
    and from the probe notes' cases, entered by hand.
  - Reported:
    - agreement on three labels and on two (supported against not);
    - Cohen's kappa;
    - agreement within each hand label;
    - every disagreement, with its claim, passages, both verdicts and the judge's reason.
  - **Not calibrated** below 20 items, or below 8 supported or 8 not supported.

## Consequences

### Positive

- **The judge targets what checks miss**: its rules name scope and wrong-item numbers, the F2 and F3
  patterns, rather than general "faithfulness".
- **Self-grading avoided**, and visible when it cannot be.
- **Trust is measured, not assumed**: kappa and per-label agreement expose a judge that is lenient or
  harsh, which overall agreement hides; the minimum stops a failures-only set from passing.
- **Calibration survives re-chunking**: passages are snapshotted, so items stay valid after a re-process.
- **Cheap to re-run**: changing only the report repeats no request; changing the judge redoes only verdicts.

### Negative

- **The judge is itself a free model**: it can be removed from the free list, rate-limited or change;
  results name the model and its prompt version, so a change is visible but old rows are not comparable.
- **Batching weakens isolation**: in experiments a claim is read beside the answer's other claims and
  their passages; calibration in single mode does not measure that effect exactly.
- **Calibration depends on the developer**: at least 20 hand verdicts, including supported ones, before
  any faithfulness figure can be called calibrated.
- **Small numbers**: 20–40 calibration items give a wide uncertainty on agreement and kappa; the report
  must show counts, not only percentages.
- **Rules can steer**: naming scope and numbers may make the judge stricter on those than a neutral judge.
  That is intended, but the agreement must show it is not over-strict.

## Alternatives Considered

- **Nemotron judging its own answers**: no extra model, but self-grading, which the spec rules out;
  rejected.
- **A smaller free model as judge** (`liquid/lfm-3-1.7b:free`, `lfm-2.5-2.6b:free`, the latter expiring
  2026-11-13): cheaper on the provider but likely too weak for scope and number distinctions; rejected.
- **One request per claim everywhere**: strict isolation, but about 140 requests per experiment instead
  of about 75; kept for calibration only (researcher's choice, 2026-11-11).
- **The guide's whole-answer judge** (one verdict for the answer against all context): cheap, but cannot
  say which claim failed, and sees passages the claim did not cite; rejected.
- **Agreement percentage alone, or a failures-only calibration set**: rewards an always-unsupported
  judge; rejected for kappa, per-label agreement and the minimum mix.
- **RAGAS faithfulness**: out of scope in the spec.

## References

- Feature Spec: [specs/005-evaluation-harness/spec.md](../../specs/005-evaluation-harness/spec.md) (FR-011–FR-016, FR-020–FR-022)
- Implementation Plan: [specs/005-evaluation-harness/plan.md](../../specs/005-evaluation-harness/plan.md)
- Research: R7, R8 and R9 in [research.md](../../specs/005-evaluation-harness/research.md);
  ClaimVerdict and CalibrationItem in [data-model.md](../../specs/005-evaluation-harness/data-model.md)
- Related ADRs: ADR-0004 (citation validation, what the judge adds to), ADR-0008 (per-part grounding;
  the scope rule the judge's rules mirror), ADR-0010 (the harness)
- Evidence: `eval/probe_notes.md` (F1, F2, F3); `docs/verification/`; Checkpoint 11 (to be recorded)
