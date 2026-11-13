# ADR-0012: Retrieval Experiments and the Relevance Gate

> **Scope**: Document decision clusters, not individual technology choices. Group related decisions that work together (e.g., "Frontend Stack" not separate ADRs for framework, styling, deployment).

- **Status:** Proposed
- **Date:** 2026-11-11
- **Feature:** 005-evaluation-harness
- **Context:**
  - **Known retrieval misses are ranking problems**: the probe found the right paper but the answer
    passage ranked low (Q2 at 11–13, Q4 at 19 in rough tests), which caused the Q2 and Q4 false
    not-founds (`eval/probe_notes.md`).
  - **Three upgrades to measure** (spec FR-024): cross-encoder reranking of the top 20, BM25 fused with
    vectors, and a title and section prefix before embedding.
  - **The gate depends on vector scores**: `RELEVANCE_THRESHOLD` (0.58) gates a question on its top vector
    score (ADR-0004) and was calibrated on bge-small cosine similarities. A reranker's logits and a fused
    rank score have other scales.
  - **One variable at a time** (FR-023): if an experiment also moved the gate, its row would mix two
    changes.
  - **Machine**: CPU only, 2 PyTorch threads, about 3 GB free memory.
  - **Licences**: candidates must allow free use.

## Decision

- **Gate unchanged**: in every retrieval experiment the gate uses the **top vector score** of the
  shortlist, so the threshold keeps its meaning and is not recalibrated. The experiments only
  **reorder or merge** passages.
- **Reranking**:
  - `cross-encoder/ms-marco-MiniLM-L6-v2` at revision `233902d25c44` (Apache-2.0, 91 MB, 2.0 s per question
    for 20 pairs on this CPU) reranks the vector top 20, and the top k are kept.
  - `cross-encoder/ms-marco-TinyBERT-L2-v2` at `81d1926f67cb` (18 MB, 0.16 s) is a second, free row.
  - Models load at their pinned revision, through sentence-transformers (already a dependency); a missing
    revision fails before anything runs.
- **Hybrid search**:
  - `rank-bm25==0.2.2` (`BM25Okapi`, k1 1.5, b 0.75) over the same passages and filter.
  - Tokens are kept whole across `-` and `.`, so names such as `gpt-3` match.
  - The two top-20 lists are fused by **reciprocal rank fusion with k = 60**, as published and not tuned.
- **Prefix**: passages are embedded as `"{title}. {section}. {text}"` with `EMBED_PREFIX` in a separate
  library. Stored text, citations and fingerprints are unchanged, so only the ranking differs.
- **Scope**: searches cover the 5 golden papers only, so other papers in the library cannot move results.
- **Adoption is separate**: these stay in the evaluation harness. Making one the default is a later
  change, which would also decide whether to recalibrate the gate.

## Consequences

### Positive

- **Clean comparisons**: each row changes only the ranking, so a gain or loss is attributable to it; the
  refusal behaviour and the threshold's calibration stay comparable across rows.
- **No recalibration debt during evaluation**: `eval/threshold_calibration.md` stays valid for every row.
- **Reproducible**: pinned revisions, a pinned BM25 version and a published fusion constant; nothing
  tuned on the golden set it is measured on.
- **Cheap**: all three experiments are local, at 0 model requests.

### Negative

- **The gate cannot benefit**: a reranker might separate relevant from irrelevant questions better than the
  vector score, but that is not measured here. Using its score for the gate would be its own experiment.
- **A BM25-only hit is always gated by the vector score**: an exact-name match that the vector search
  ranks low still depends on the question's best vector score to pass.
- **Latency matters if adopted**: MiniLM-L6 adds about 2 s per question on this CPU; acceptable for an
  evaluation, worth weighing for the product (TinyBERT's row shows the cheaper option).
- **rank-bm25 is unmaintained** (last release 2022): it is small and pinned, but a future Python or numpy
  change could break it.
- **Larger rerankers untested**: bge-reranker-base and v2-m3 do not fit this machine's memory, and
  mxbai-rerank-xsmall loads in half precision on CPU and did not finish in time, so the best model
  available today may not be among those measured.

## Alternatives Considered

- **Gate on the reranker or fused score**: possibly better refusals, but a new threshold to calibrate and
  a second variable in the row; rejected for now, possible as a later experiment.
- **Recalibrate the threshold per experiment**: comparable refusals at each row's best, but every
  retrieval row would then change two things; rejected.
- **Weighted score fusion, or CombSUM/CombMNZ**: needs score normalisation and a weight tuned on the
  golden set; rejected for rank-only RRF.
- **Tuning RRF's k on the golden set**: overfits about 40 questions; rejected.
- **MiniLM-L12-v2 as the reranker**: no better than L6 on the probes, at 5.8 s per question; rejected.
- **bge-reranker-base or v2-m3**: 1.1 and 2.3 GB, beyond this machine's free memory; not testable here.
- **jina-reranker-v2-base-multilingual**: CC-BY-NC licence; excluded.
- **Prefix stored in the passage text**: changes what the model reads and cites, so two things vary;
  rejected.

## References

- Feature Spec: [specs/005-evaluation-harness/spec.md](../../specs/005-evaluation-harness/spec.md) (FR-006–FR-008, FR-023, FR-024)
- Implementation Plan: [specs/005-evaluation-harness/plan.md](../../specs/005-evaluation-harness/plan.md)
- Research: R3, R4, R5 and R6 in [research.md](../../specs/005-evaluation-harness/research.md)
- Related ADRs: ADR-0001 (local retrieval stack), ADR-0004 (the relevance gate), ADR-0010 (the harness)
- Evidence: reranker timings of 2026-11-11 (research R4); `eval/probe_notes.md`;
  `eval/threshold_calibration.md`; Checkpoint 11 (to be recorded)
