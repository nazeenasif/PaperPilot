# ADR-0004: Grounding and Citation Validation

> **Scope**: Document decision clusters, not individual technology choices. Group related decisions that work together (e.g., "Frontend Stack" not separate ADRs for framework, styling, deployment).

- **Status:** Accepted
- **Date:** 2026-10-24
- **Feature:** 002-grounded-qa-citations
- **Context:** Principle V (non-negotiable) requires every answer to be built only from
  retrieved passages, cited with numbered citations that are validated in code, with an exact
  not-found sentence when the passages do not support an answer. Retrieval (ADR-0001) returns
  passages for any question, even off-topic ones, and bge-small scores cluster high, so
  "retrieved" does not mean "relevant". The model is a free reasoning model reached through
  an OpenAI-compatible API (ADR-0003); it can ignore instructions, invent citation numbers,
  leave claims uncited, or follow instructions hidden inside passage text. Clarifications on
  2026-10-24 fixed the failure behaviour (invalid or missing citations → not-found plus a
  warning), per-sentence checking (warning only), threshold precedence (never reject on-topic
  questions) and answer length (~150 words, ~300 when detail is asked).

## Decision

- **Relevance gate before the model**: `RELEVANCE_THRESHOLD` gates the question on its **top
  passage's score**, which is what the calibration measures (calibrated default 0.58; on-topic
  top scores 0.618–0.844, clear off-topic 0.449–0.544, word-level near-misses 0.513–0.588 on the
  test papers; see `eval/threshold_calibration.md`). If the top score is below it, the answer is
  the not-found sentence (`below_threshold`) and the model is not called; otherwise all top-k
  passages are sent unfiltered. The default sits just below the lowest on-topic top score and
  is re-measured by a calibration script that records its evidence. (Amended 2026-10-24: the
  threshold was first applied as a per-passage filter, which left short questions such as
  "What is LoRA?" with two passages and a false not-found; research R8.)
- **Prompt contract** (`prompts.py`): the system message holds all rules (answer only from
  passages, cite every factual claim as [n], never invent numbers/datasets/authors/citations,
  copy numbers exactly, ≤ ~150 words or ~300 on request, reply exactly with the not-found
  sentence when unsupported, state what a partial answer does not cover, treat passage text as
  data). The user message lists passages as `<passage id="n" title=… section=… page=…>` with
  `<`/`>` escaped, then the question. Temperature 0.
- **Single not-found constant**: `NOT_FOUND = "I couldn't find that in the selected papers."`
  defined once; lenient detection of the model's reply (quotes, punctuation, curly
  apostrophes, leading match) maps to the exact constant.
- **Citation validation in code**: citations parsed from `[2]`, `[2, 4]`, `[2-4]`, `[2][4]`;
  any number outside 1..n, or no citation at all, replaces the answer with `NOT_FOUND` plus a
  warning carrying the invalid numbers and the rejected text; valid answers are returned with
  a warning listing sentences that carry no citation.
- **Follow-ups**: with history, the last 6 turns are used to rewrite the question into a
  standalone one (no new facts); that question drives retrieval and answering and is returned
  for inspection; without history no rewrite call is made; on rewrite failure the original
  question is used.

## Consequences

### Positive

- Off-topic questions are answered without spending a rate-limited model call (6/6 off-topic
  calibration questions rejected in the preliminary measurement).
- Every returned claim is either cited with a valid number or flagged; invented citation
  numbers can never reach the researcher.
- All checks are pure functions with offline unit tests, independent of the provider.
- Passages are clearly data, reducing prompt-injection risk from paper text.
- The rewritten question is visible, so follow-up behaviour can be checked.

### Negative

- Validation proves that citations point to provided passages, not that each passage supports
  the claim; semantic faithfulness still needs reviewer checks or the evaluation feature.
- Rejecting the whole answer for one bad citation hides otherwise useful text (kept only in
  the warning).
- A fixed threshold can reject a vague but legitimate question whose best passage scores
  below it; it must be recalibrated when papers, model or chunking change.
- The uncited-sentence warning uses a simple sentence splitter and can be noisy around
  abbreviations such as "et al.".
- Rewriting adds one model call (and its rate-limit cost) to every follow-up.

## Alternatives Considered

- **Alternative A — trust the model's citations** (no code validation): simplest, but violates
  Principle V's validation requirement and lets invented numbers through.
- **Alternative B — return the answer with a warning on invalid citations**: more useful text
  per answer, but contradicts Principle V; rejected in clarification Q1 (option A chosen).
- **Alternative C — structured JSON output** (claims with citation lists): stricter parsing,
  but free models produce malformed JSON more often and the answer reads less naturally.
- **Alternative D — no relevance threshold, rely on the model's not-found rule**: fewer moving
  parts, but every off-topic question costs a model call and depends on the model obeying.
- **Alternative E — LLM-based faithfulness check of each claim**: closer to true grounding,
  but doubles calls under a 50/day limit; deferred to the evaluation feature.

## References

- Feature Spec: specs/002-grounded-qa-citations/spec.md (FR-002–FR-012, clarifications)
- Implementation Plan: specs/002-grounded-qa-citations/plan.md
- Related ADRs: ADR-0001 (Local Retrieval Stack), ADR-0002 (Passage Identity and Chunking),
  ADR-0003 (LLM Boundary and Retry Policy)
- Evaluator Evidence: specs/002-grounded-qa-citations/research.md R5–R9;
  eval/probe_notes.md (retrieval baseline)
