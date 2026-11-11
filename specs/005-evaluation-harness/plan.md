# Implementation Plan: Evaluation Harness

**Branch**: `005-evaluation-harness` | **Date**: 2026-11-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/005-evaluation-harness/spec.md`

## Summary

A separate `evaluation` package measures PaperPilot against a committed golden set
(`eval/golden.json`, about 40 questions with evidence phrases by paper and page, never passage IDs).

- **Matching**: evidence matches passages by normalised, hyphen-insensitive text (research R1, R2).
- **Retrieval**: evaluation is local and costs 0 requests. It reports hit@k, MRR and the gated
  not-founds, per question kind, for four experiments:
  - reranking the vector top 20 with a pinned cross-encoder (MiniLM-L6-v2, plus TinyBERT-L2 as a cheap second row);
  - BM25 fused with vectors by reciprocal rank fusion, k = 60;
  - a title and section prefix embedded into a separate library.

  The baseline library is never touched (R3–R6).
- **Answers**: evaluation runs the real `service.ask` through a small `retrieve` seam (R12). A
  different free model, `google/gemma-4-31b-it:free` (verified on today's free list), judges claims
  against only their cited passages and returns supported, partly or unsupported with a reason. It
  goes through `llm.generate`, the only LLM boundary, and everything is cached by claim, passages,
  judge model, prompt version and mode (R7, R8).
- **Calibration**: the judge is checked one claim per request against hand verdicts imported from the
  reports' Verdict column and the probe notes' failure cases. Agreement and kappa are reported per
  label, and every disagreement is listed (R9).
- **Sessions**: runs are planned in units, take a slice of the day's quota, keep a reserve of 10 and
  resume across days (R10).
- **Results**: rows are stored per experiment with the full configuration in `eval/results/`, and
  `eval report` generates `eval/results.md` and the README table from those files only (R11).

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: existing: sentence-transformers 6.2.0 (also loads the cross-encoders),
torch 2.14.1+cpu, ChromaDB 1.5.9, PyMuPDF 2.0, openai SDK inside `llm.py`. **New: `rank-bm25==0.2.2`**
(Apache-2.0, numpy only; the hybrid experiment, research R5). No new frontend code.
**Storage**: `eval/golden.json`, `eval/experiments.json`, `eval/calibration.json`, `eval/results/*.json`
(committed, no paper text in results); `data/eval/eval.sqlite3` (gitignored cache: answers,
verdicts, progress); `data/eval/libraries/prefix/` (gitignored, the prefix experiment's library)
**Testing**: pytest under `tests/evaluation/` with the scripted LLM, the fake embedder, a tiny fake
cross-encoder and fixture PDFs; no network, no model. The real checkpoint is the CLI itself (Checkpoint 11).
**Target Platform**: Windows dev machine, CPU only (2 PyTorch threads measured), about 3 GB free memory
**Project Type**: a separate Python package beside the engine, CLI only
**Performance Goals**: a full golden retrieval run per experiment in under 2 minutes with the
MiniLM-L6 reranker (2.0 s per question measured), seconds without it; a report in under 5 s
**Constraints**: about 50 free requests a day, a reserve of 10; every model call inside its output
limit; the researcher's library, saved results and defaults unchanged (SC-009)
**Scale/Scope**: about 40 golden questions, 5 papers, 220 passages; 8 experiments (5 retrieval, 3 optional)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle (v1.3.0) | Check | Status |
|---|---|---|
| I. Plain, typed code | Plain Python with type hints and docstrings; no framework; rank-bm25 is a library, not orchestration | ✅ |
| II. Modular package, single LLM boundary | The harness is a separate package outside the module list, like the API adapter: it imports `paperpilot` and is never imported by it. Engine seams stay in their modules (R12). The judge calls `llm.generate(model=...)`, so only `llm.py` talks to an LLM | ✅ (see Complexity Tracking) |
| III. OpenAI-compatible, free by default | The judge and second model are free models set by settings (`EVAL_JUDGE_MODEL`, `LLM_MODEL`); no provider JSON mode required | ✅ |
| IV. Local embeddings, persistent store | Embeddings stay `bge-small-en-v1.5`; the prefix library is a separate persistent store; the researcher's library is never re-embedded | ✅ |
| V. Grounded answers (NON-NEGOTIABLE) | Answers come from the unchanged pipeline with validation; the harness only measures, and the judge adds a check, never relaxes one | ✅ |
| VI. Secrets and data hygiene | The cache holds passage text and lives under gitignored `data/`; committed results carry no paper text or keys; no PDFs committed | ✅ |
| VII. Testable checkpoints, measured quality | This feature is the eval harness the principle requires; its pure logic (normalisation, metrics, fusion, parsing, planning, agreement) is unit-tested offline | ✅ |
| VIII. Simplicity, small commits | One new dependency, justified (R5); JSON not YAML; seams default to today's behaviour | ✅ |
| IX. Visible grounding in a web interface | No UI change; the harness is a maintenance script, which the principle allows | ✅ |

**Post-design re-check (after Phase 1)**: unchanged. The contracts add one optional argument each to
`service.ask`, `llm.generate`, `service.summarize` and `service.compare`, five settings and one task
kind, all defaulting to today's behaviour.

## Project Structure

### Documentation (this feature)

```text
specs/005-evaluation-harness/
├── spec.md
├── plan.md              # this file
├── research.md          # R1–R12
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md           # python -m evaluation
│   └── engine-api.md    # the engine seams and settings
├── checklists/requirements.md
└── tasks.md             # /sp.tasks
```

### Source Code (repository root)

```text
evaluation/                 # new package; imports paperpilot, never imported by it
├── __init__.py
├── __main__.py             # CLI (contracts/cli.md)
├── golden.py               # load, normalise, validate (R1, R2)
├── retrieval.py            # vector, rerank, hybrid; rank, hit@k, MRR, gating (R3–R5)
├── libraries.py            # the prefix library build (R6)
├── answers.py              # answers through service.ask, claims (R8)
├── judge.py                # judge prompt, parse, cache key (R7)
├── calibration.py          # import from reports, agreement, kappa (R9)
├── runs.py                 # units, plan, slice, reserve, resume (R10)
├── store.py                # data/eval/eval.sqlite3 (R11)
├── experiments.py          # configuration, one-variable check (R11)
└── report.py               # eval/results.md and the README block (R11)

paperpilot/                 # seams only (contracts/engine-api.md)
├── config.py               # USAGE_DIR, EMBED_PREFIX, SCOPE_RULE, EVAL_JUDGE_MODEL, EVAL_RESERVE
├── llm.py                  # generate(model=...), task "judge"; usage under USAGE_DIR
├── library.py              # embed with the prefix when EMBED_PREFIX
├── prompts.py              # instructions with or without SCOPE_RULE
└── service.py              # ask(retrieve=...), summarize/compare(save=...)

eval/                       # committed data
├── golden.json
├── experiments.json
├── calibration.json
├── results/<experiment>.json
├── results.md              # generated
└── probe_notes.md …        # existing

tests/evaluation/           # offline tests
```

**Structure Decision**: a sibling package keeps experiment code (reranking, hybrid search, the judge)
out of the engine until a later change adopts a result (FR-026), and it can be run as
`python -m evaluation`. The committed `eval/` folder already holds the probe notes and calibration
records, so the golden set and results sit beside them.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| A package outside Principle II's module list (`evaluation/`) | The harness has about ten responsibilities that are not product code; placed in `service` or `library` they would ship experimental retrieval and a judge inside the engine | Scripts under `scripts/` (no shared, testable modules for about 1,000 lines); adding modules to `paperpilot` (the principle fixes its module list, and the judge would sit beside the product's grounding code) |

## Architecture Decisions

📋 Architectural decisions detected:

1. **An evaluation package beside the engine, with default-preserving seams** (`retrieve`, `model`,
   `save`, five settings). Long-term: it decides where experimental retrieval lives until adopted.
   Document reasoning and tradeoffs? Run `/sp.adr evaluation-harness-architecture`
2. **The LLM judge: a different free model, claims against cited passages only, per-claim calibration
   against hand verdicts with a minimum and kappa, cached by claim, passages, model, version and mode.**
   This is what the faithfulness numbers rest on. Document? Run `/sp.adr llm-judge-and-calibration`
3. **Retrieval experiments without recalibrating the gate**: reranking and RRF reorder only, and the
   gate stays on the vector top score; the reranker revision and RRF k = 60 are pinned. A later
   adoption depends on it. Document? Run `/sp.adr retrieval-experiments-and-gate`

The golden-set format and session slicing are reversible, local choices covered by research R1 and
R10, and do not need ADRs.
