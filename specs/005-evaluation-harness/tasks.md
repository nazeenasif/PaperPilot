---
description: "Task list for Feature 5, the evaluation harness"
---

# Tasks: Evaluation Harness

**Input**: Design documents from `specs/005-evaluation-harness/` (plan.md, spec.md, research.md,
data-model.md, contracts/cli.md, contracts/engine-api.md, quickstart.md); ADR-0010, ADR-0011, ADR-0012.

**Tests**: required. Every implementation task is preceded by a failing-test task. Tests run offline
with the scripted LLM (`tests/conftest.py` `ScriptedLLM`, `fake_answers`), the fake embedder and a fake
cross-encoder. No test may call the real model, the provider's key endpoint or download a model.

**Commits**: one commit per task; messages name the files and end with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

**Requests**: every task that sends real model requests states its planned count in **bold** and runs
in sessions (a slice of today's quota, keeping the reserve of 10). Every other task makes 0 requests.

**Human tasks** are marked **HUMAN** and are done by the researcher; Claude Code may prepare drafts but
never marks them done.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1 golden set, US2 retrieval, US3 answers, US4 judge, US5 experiments and results,
  US6 sessions (spec.md)

## Path Conventions

- Harness: `evaluation/` (sibling package, ADR-0010); its tests: `tests/evaluation/`
- Engine seams: `paperpilot/`; their tests: `tests/`
- Committed data: `eval/`; gitignored cache and libraries: `data/eval/`

---

## Phase 1: Setup

- [X] T001 Add `rank-bm25==0.2.2` to `requirements.txt`, install it into `.venv`, and create the package skeleton: `evaluation/__init__.py`, `evaluation/__main__.py` (argparse with the subcommands of contracts/cli.md, each printing "not implemented" and exiting 2), `tests/evaluation/__init__.py`, and `tests/evaluation/conftest.py` re-using the root fixtures. Confirm that `git check-ignore data/eval/eval.sqlite3` passes. 0 requests.
- [X] T002 [P] Create `eval/experiments.json` with the experiments of data-model.md (`baseline`, `rerank-minilm-l6`, `rerank-tinybert`, `hybrid-rrf60`, `prefix`, `reasoning-low`, `gemma`, `scope-rule-off`): each has its `changes`, `answers` (true only for the baseline), `optional` (true for the last three), `set`, `runs` and `takeaway: null`. 0 requests.

---

## Phase 2: Foundational (blocks every story)

**Purpose**: the engine seams of contracts/engine-api.md, the harness cache and the configuration record. Each seam defaults to today's behaviour.

- [X] T003 [P] Write failing tests in `tests/test_config_eval.py` for the settings `USAGE_DIR` (default `LIBRARY_DIR`), `EMBED_PREFIX` (default false), `SCOPE_RULE` (default true), `EVAL_JUDGE_MODEL` (default `google/gemma-4-31b-it:free`) and `EVAL_RESERVE` (default 10, must be ≥ 0). Bad values raise `SettingsError`, and `usage.sqlite3` is opened under `USAGE_DIR`.
- [X] T004 Implement the settings in `paperpilot/config.py`, and open the usage database under `USAGE_DIR` in `paperpilot/llm.py`, so that T003 passes and the existing tests are unchanged.
- [X] T005 [P] Write failing tests in `tests/test_llm_model_arg.py`, using `fake_llm.FakeClient`:
  - `llm.generate(..., model="x/y:free")` sends that model;
  - with no `model`, it sends `LLM_MODEL` as today;
  - the request is counted and retried as any other;
  - `OUTPUT_TOKENS["judge"] == 8192`;
  - a cut-off judge reply raises `LLMError(reason="cut_off")` with tokens.
- [X] T006 Implement the `model` argument and task kind `judge` in `paperpilot/llm.py` so that T005 passes.
- [X] T007 [P] Write failing tests in `tests/test_ask_retrieve.py`:
  - with no `retrieve`, `service.ask` calls `library.search` exactly as before (spy), and the existing `tests/test_ask*.py` stay green;
  - a custom `retrieve` returning `Retrieval(passages, gate_score)` is used for the passages, and the gate compares `gate_score` with the threshold even when the passages' own scores are lower;
  - `gate_score=None` with no passages gives not-found with 0 requests.
- [X] T008 Implement `Retrieval` and the `retrieve` argument of `ask` in `paperpilot/service.py` so that T007 passes.
- [X] T009 [P] Write failing tests in `tests/evaluation/test_eval_store.py` for `evaluation/store.py`:
  - answers are stored and loaded by configuration hash, question id and run index;
  - verdicts are stored by key, and a `not_judged` verdict is never returned as final;
  - run progress (planned, done, requests, sessions) survives reopening;
  - two processes writing at once lose nothing (WAL, `BEGIN IMMEDIATE`);
  - the file lives under `data/eval/` of the given root.
- [X] T010 Implement `evaluation/store.py` (SQLite at `data/eval/eval.sqlite3`) so that T009 passes.
- [X] T011 [P] Write failing tests in `tests/evaluation/test_experiments.py` for `evaluation/experiments.py`:
  - `configuration()` records every field of data-model.md's Configuration, with instruction hashes taken from `prompts`;
  - `answer_hash()` covers only answer-relevant fields;
  - `one_change(baseline, other)` ignores the derived fields (`paper_fingerprints`, `commit`) and names each difference, and two or more differences are refused;
  - `eval/experiments.json` loads, and a malformed entry fails with its name.
- [X] T012 Implement `evaluation/experiments.py` so that T011 passes.

**Checkpoint**: full `pytest` passes; the engine behaves as before when no new argument or setting is used.

---

## Phase 3: User Story 1 — golden set (P1) 🎯 MVP

**Goal**: a validated golden set of 12 questions over the 5 papers (reduced 2026-11-13 from 30–50).
**Independent test**: `python -m evaluation check` reports counts per kind and fails for a wrong page, an unmatched phrase or a passage ID, with 0 requests.

- [X] T013 [US1] Write failing tests in `tests/evaluation/test_golden.py`:
  - **Normalisation**: `normalise` unfolds `ﬁ`/`ﬂ`, joins line-break hyphens, removes hyphens so that "pre-training" matches "pretraining", and keeps `%`, `±`, `.` and `×` (research R2).
  - **Loading**: the schema of data-model.md loads, and full-line `//` comments are ignored.
  - **The check fails**, naming the question, for each of:
    - a phrase that matches no stored passage of its paper (fixture PDF in the temporary library, fake embedder);
    - a phrase that is not on its stated page;
    - an unknown arXiv ID;
    - a field holding `<12 hex>-<n>`;
    - an answerable question without evidence;
    - a `table: true` question whose evidence is not in a table passage;
    - counts below the targets (reduced 2026-11-13 to 2 single-paper per paper and 2 near-miss; other kinds optional; table answers counted, not required);
    - any item with `"confirmed": false` (unless `--drafts`).
  - **Empty file**: the check reports 0 of each target and fails, with 0 requests.
  - **Re-chunking**: the check passes again after the library is rebuilt with other chunk settings.
- [X] T014 [US1] Implement `evaluation/golden.py` and the `check` command in `evaluation/__main__.py` so that T013 passes.
- [X] T015 [US1] Create the empty golden set and its guide (0 requests; Claude Code):
  - `eval/golden.json`: `"version": 0` and `"questions": []`, with a commented example item of every kind above the list, as `//` lines that the loader ignores.
  - `eval/GOLDEN_GUIDE.md`, in short:
    - the question kinds and the target counts;
    - the fields;
    - how `scope`, `table`, `turns` and `standalone` work;
    - what makes a good near-miss;
    - why there are no passage IDs;
    - that evidence is drafted afterwards for confirmation.
- [X] T016 [US1] ~~**HUMAN**~~ (reassigned to Claude Code by the researcher, 2026-11-13): write the golden questions in `eval/golden.json`, following `eval/GOLDEN_GUIDE.md`:
  - **Counts** (reduced 2026-11-13): 12 questions: 2 single-paper per paper (10) and 2 near-miss. Table answers are welcome but not required; cross-paper, off-topic and follow-up questions are optional extras.
  - **Fields**: `id`, `kind`, `question`, `scope`, `papers`, `expected` and `table`; `turns` and `standalone` for follow-ups.
  - **Evidence**: none needed yet.
  - **Known cases**: optional (FR-005 is future work); the Q2 and Q4 false not-founds may be among the 12, with `known_case`.
- [X] T017 [US1] Draft evidence for every answerable question (0 requests; Claude Code):
  - one or two phrases copied from the PDF, each with its page, that match a stored passage of the paper (in a table passage for `table: true`), checked by `check --drafts`;
  - every item is set `"confirmed": false`;
  - a question whose answer cannot be found in the paper is listed for the researcher, not given invented evidence.
- [X] T018 [US1] ~~**HUMAN**~~ (reassigned to Claude Code by the researcher, 2026-11-13; the researcher reviews the drafted set): confirm each evidence phrase and page against the PDF, correct any, set `"confirmed": true` per item, and set `version` to 1.
- [X] T019 [US1] Run `python -m evaluation check` (0 requests); it must pass with no `--drafts`. Commit `eval/golden.json`.

---

## Phase 4: User Story 2 — retrieval rows (P1), 0 requests

**Goal**: hit@k, MRR and gated not-founds for the baseline, the two rerankers, hybrid search and the prefix, without touching the library.
**Independent test**: `python -m evaluation retrieval` writes five rows with 0 model requests, identical on a repeat run, and the library's fingerprints are unchanged.

- [X] T020 [P] [US2] Write failing tests in `tests/evaluation/test_retrieval_metrics.py`:
  - **Rank**: for a single-paper question, the rank is the first relevant passage. For a cross-paper question, it is the position by which every required paper is covered, and it is none if one paper is missing within 20.
  - **Metrics**: hit@1/3/6/10, MRR (0 when not found), and both per kind.
  - **Follow-ups**: they use `standalone`.
  - **Gating**: near-miss and off-topic questions count as gated when the top vector score is under the threshold.
  - **Scope**: searches are restricted to the golden papers, or the one paper for `scope: paper`.
- [X] T021 [US2] Implement the metrics and the vector retriever (shortlist 20, then the top k; the gate score is the top vector score) in `evaluation/retrieval.py` so that T020 passes.
- [X] T022 [P] [US2] Write failing tests in `tests/evaluation/test_retrieval_run.py`: `retrieval baseline` writes `eval/results/baseline.json` with the configuration, the golden version and hash, metrics overall and per kind, per-question ranks and no passage text. A second run gives the same numbers, the library's passage fingerprints and `results.sqlite3` are unchanged, and the request counter does not move.
- [X] T023 [US2] Implement the `retrieval` command and the result writer in `evaluation/retrieval.py` and `evaluation/__main__.py` so that T022 passes.
- [X] T024 [US2] Run `python -m evaluation retrieval baseline` (0 requests); show hit@6, MRR and per-kind figures; commit `eval/results/baseline.json`.
- [ ] T025 [P] [US2] Write failing tests in `tests/evaluation/test_rerank.py`, with a fake cross-encoder:
  - it reorders the vector top 20 and keeps the top k;
  - the gate score stays the vector top score;
  - the model is loaded with its pinned name and revision;
  - a load failure stops the experiment before any question;
  - the configuration records the reranker and revision.
- [ ] T026 [US2] Implement reranking in `evaluation/retrieval.py` with `sentence_transformers.CrossEncoder(name, revision=..., device="cpu")`, for `cross-encoder/ms-marco-MiniLM-L6-v2@233902d25c44` and `cross-encoder/ms-marco-TinyBERT-L2-v2@81d1926f67cb`, so that T025 passes.
- [ ] T027 [P] [US2] Write failing tests in `tests/evaluation/test_hybrid.py`:
  - **Tokens**: `gpt-3`, `sst-2` and `v1.1` stay whole, and NFKC and lower case apply.
  - **BM25**: it runs over exactly the scoped passages, with `BM25Okapi` k1 1.5 and b 0.75.
  - **Fusion**: RRF with k = 60 on two known lists gives the expected order and ties.
  - **Gate**: it stays the vector top score.
  - **Configuration**: it records `rrf_k`, `bm25` and the rank-bm25 version.
- [ ] T028 [US2] Implement hybrid search in `evaluation/retrieval.py` so that T027 passes.
- [ ] T029 [P] [US2] Write failing tests:
  - `tests/test_embed_prefix.py`: with `EMBED_PREFIX` on, `library.add_paper` embeds `"{title}. {section}. {text}"` (spy on the embedder) while the stored text, passage IDs and fingerprint equal the unprefixed ones; it is off by default.
  - `tests/evaluation/test_libraries.py`: `build_prefix_library(root)` ingests the papers into `data/eval/libraries/prefix/` under its own `LIBRARY_DIR` with `USAGE_DIR` at the main library, is reused when already built for the same settings, and leaves the main library unchanged.
- [ ] T030 [US2] Implement the prefix in `paperpilot/library.py` and `evaluation/libraries.py`, and the `prefix` experiment in `evaluation/retrieval.py`, so that T029 passes.
- [ ] T031 [US2] Run `python -m evaluation retrieval rerank-minilm-l6 rerank-tinybert hybrid-rrf60 prefix` (0 requests; the first run downloads 91 MB and 18 MB of reranker weights and builds the prefix library). Show the five rows side by side, confirm that the main library's fingerprints are unchanged, and commit `eval/results/*.json`.

---

## Phase 5: User Story 5 — the best-configuration rule (P2), 0 requests — FUTURE WORK

> **Future work (2026-11-13)**: out of the reduced scope (spec, "Scope (2026-11-13)"). Kept for a later feature; not built or run now, and `/sp.implement` skips `[FUTURE]` tasks.

**Goal**: one documented choice of what gets answer evaluation (FR-024b).
**Independent test**: `python -m evaluation best` prints the winner and its figures from stored rows.

- [ ] T032 [FUTURE] [US5] Write failing tests in `tests/evaluation/test_best.py`:
  - the winner is the highest hit@6, with ties broken by MRR;
  - a row that does not beat the baseline cannot win, so the result is "baseline";
  - optional rows are ignored;
  - `best --choose NAME` overrides the rule and records why;
  - the choice is written to `eval/experiments.json` (`answers: true`).
- [ ] T033 [FUTURE] [US5] Implement the `best` command in `evaluation/experiments.py` and `evaluation/__main__.py` so that T032 passes; run it (0 requests) and commit `eval/experiments.json`.

---

## Phase 6: User Story 6 — sessions that fit the free tier (P2) — FUTURE WORK

> **Future work (2026-11-13)**: out of the reduced scope (spec, "Scope (2026-11-13)"). Kept for a later feature; not built or run now, and `/sp.implement` skips `[FUTURE]` tasks.

**Goal**: runs planned in units, sliced per day, keeping the reserve, resumable.
**Independent test**: with scripted usage near the limit, a run refuses with 0 requests; a scripted run stopped midway resumes without repeating finished units.

- [ ] T034 [FUTURE] [US6] Write failing tests in `tests/evaluation/test_runs.py`, with a fake `llm.usage` and the scripted LLM:
  - **Planning**: the plan counts units (an answer is 1, a follow-up 2, a judge request 1) and subtracts cached units.
  - **Default slice**: today's remaining less `EVAL_RESERVE`, up to the work left; `--slice N` sets it.
  - **Refusal**: a session refuses with 0 requests when the remaining less the reserve is below its plan, and says when requests resume.
  - **Per unit**: each unit starts only if both the slice and the remaining less the reserve cover it, so retries cannot spend the reserve.
  - **Stopping**: `DailyLimitError`, `RateLimitedError` and a busy model end the session with its reason recorded; a later session resumes, repeating no finished unit.
  - **Counting**: retries are counted apart from planned requests.
- [ ] T035 [FUTURE] [US6] Implement `evaluation/runs.py` and the `status` command so that T034 passes.

---

## Phase 7: User Story 4 — judge and calibration (P2) — FUTURE WORK

> **Future work (2026-11-13)**: out of the reduced scope (spec, "Scope (2026-11-13)"). Kept for a later feature; not built or run now, and `/sp.implement` skips `[FUTURE]` tasks.

**Goal**: a judge whose agreement with hand verdicts is known before its numbers are used.
**Independent test**: `calibrate` on stored items reports agreement, kappa and per-label agreement, lists every disagreement, and repeats as 0 requests from the cache.

- [ ] T036 [FUTURE] [US4] Write failing tests in `tests/evaluation/test_judge.py`, with the scripted LLM:
  - **Request content**: it holds only the claims and their own cited passages, with tags escaped; never the question, the expected answer, other claims' passages or the answering model.
  - **Modes**: single mode sends one claim; batch mode lists each claim beside its own passages.
  - **Rules**: the instruction names scope, wrong-item numbers and "passages only".
  - **Parsing**: plain JSON, fenced JSON and surrounding text all parse.
  - **Not judged**: a missing claim, an unreadable reply or a cut-off gives `not_judged`, which is never supported.
  - **Cache key**: it changes with each of the claim, the passages, the judge model, `JUDGE_PROMPT_VERSION` and the mode.
  - **Self-grading**: it is flagged when the judge model equals the answerer.
- [ ] T037 [FUTURE] [US4] Implement `evaluation/judge.py` (`JUDGE_INSTRUCTION`, `JUDGE_PROMPT_VERSION = 1`, `build_judge_prompt`, `parse_verdicts`, `judge_claims` calling `llm.generate(model=EVAL_JUDGE_MODEL, task="judge")`) so that T036 passes.
- [ ] T038 [FUTURE] [US4] Write failing tests in `tests/evaluation/test_calibration.py`:
  - **Import**: `calibrate import` parses a verification report's table and maps the Verdict column (`correct`, `partly`, `wrong`), skipping empty verdicts. Each cited excerpt is matched by normalised prefix to a stored passage and its full text snapshotted; an unmatched excerpt is listed and its item skipped, never guessed.
  - **Metrics**: agreement on three labels and on two, Cohen's kappa against hand-computed values, and agreement per hand label.
  - **Disagreements**: `eval/calibration.md` lists every disagreement with the claim, passages, both verdicts and the reason.
  - **Minimum**: below 20 items, or fewer than 8 supported or 8 not supported, the report says "not calibrated".
  - **Requests**: calibration sends one request per item through `runs`, and a repeat costs 0.
- [ ] T039 [FUTURE] [US4] Implement `evaluation/calibration.py` and the `calibrate import` and `calibrate` commands so that T038 passes.
- [ ] T040 [FUTURE] [P] [US4] Write the known-case items into `eval/calibration.json` (0 requests; Claude Code), with passage text snapshotted from the store or quoted in `eval/probe_notes.md`, and the hand verdict that the notes already record:
  - F1;
  - F2 (the four occurrences and the v4 Data claim 9 variant);
  - F3 (LoRA claims 12, 14 and 15, and comparison claim 11);
  - the off-aspect RAG Limitations cell;
  - claim 5's incomplete citations.

  Include each item's `source`.
- [ ] T041 [FUTURE] [US4] **HUMAN**: fill the **Verdict** column of the verification reports in `docs/verification/` (at least 5 claims from each of the LoRA summary and the BERT–RAG comparison, per Feature 4's SC-002), so that with T040's items there are at least 20, including at least 8 supported and 8 not supported. Fill **Fault** for wrong claims.
- [ ] T042 [FUTURE] [US4] Run `python -m evaluation calibrate import` on each filled report (0 requests); report unmatched excerpts; commit `eval/calibration.json`.
- [ ] T043 [FUTURE] [US4] Run `python -m evaluation calibrate` in sessions. **Planned requests: one per calibration item**, at least 20; the exact figure is the item count printed by the plan, expected 25–35. Show agreement, kappa, per-label agreement and the disagreements; commit `eval/calibration.md`.

---

## Phase 8: User Story 3 — answer evaluation for the baseline and the winner (P1) — FUTURE WORK

> **Future work (2026-11-13)**: out of the reduced scope (spec, "Scope (2026-11-13)"). Kept for a later feature; not built or run now, and `/sp.implement` skips `[FUTURE]` tasks.

**Goal**: citation validity, refusals and judged faithfulness for the baseline and the best retrieval configuration.
**Independent test**: with the scripted LLM, a run over a few questions stores answers and verdicts, and a repeat costs 0 requests with identical numbers.

- [ ] T044 [FUTURE] [US3] Write failing tests in `tests/evaluation/test_answers.py`, with the scripted LLM:
  - **Pipeline**: answers come from `service.ask` with the experiment's `retrieve` and settings; a follow-up passes `turns` as history.
  - **Claims**: they follow the validator's sentence rule; uncited sentences are not judged and count as uncited.
  - **Scoring**: citation validity, correct refusal, false not-found, and the faithfulness counts (supported, partly, unsupported, uncited, not judged).
  - **Judging**: one judge request per answer with at least one cited claim, and none for a correct refusal.
  - **Caching**: a repeat costs 0 and gives the same numbers; an answer under another configuration is not reused; a new judge version re-judges only.
  - **Results**: `eval/results/<name>.json` gains its `answers` block, with no passage text.
- [ ] T045 [FUTURE] [US3] Implement `evaluation/answers.py` and the `answers` and `judge` commands (both run through `runs`) so that T044 passes.
- [ ] T046 [FUTURE] [US3] Run `python -m evaluation answers baseline` then `judge baseline` in sessions over days. **Planned requests: about 70** (one per question, two per follow-up, so about 40, plus one judge request per answer with a cited claim, about 29). The exact figure is printed before any request. Show the answer metrics and commit `eval/results/baseline.json`.
- [ ] T047 [FUTURE] [US3] If `best` chose an experiment other than the baseline, run `answers` and `judge` for it. **Planned requests: about 75**, as T046. If the baseline won, record "no winner over the baseline" in `eval/experiments.json` and send 0 requests. Commit.

---

## Phase 9: User Story 5 — report and README (P2), 0 requests

**Goal**: the results table generated from stored results, in `eval/results.md` and the README.
**Independent test**: `report` twice produces identical files from `eval/results/` and `eval/experiments.json` alone.

- [ ] T048 [US5] Write failing tests in `tests/evaluation/test_report.py`:
  - **Rows**: one per experiment, from result files only (no cache, no PDFs). Unmeasured answer columns read "not measured", a row without a takeaway says so, a row from another golden version or hash is marked "earlier golden set", and a self-graded row is marked.
  - **Content**: per-kind tables, the calibration line reading "not measured (future work)" when there is no calibration, and the set's size and limits.
  - **README**: the block between `<!-- eval-results:start -->` and `<!-- eval-results:end -->` is replaced, or appended when absent, and a second run changes nothing.
- [ ] T049 [US5] Implement `evaluation/report.py` and the `report` command so that T048 passes.
- [ ] T050 [US5] **HUMAN**: write the `takeaway` of the baseline and of at least two experiments in `eval/experiments.json`.
- [ ] T051 [US5] Run `python -m evaluation report` (0 requests); commit `eval/results.md` and `README.md`.

**Checkpoint 11 (reduced 2026-11-13)**: a 12-question golden set, a baseline row and at least two retrieval experiments with written conclusions, and the README table generated from stored results, with answer columns reading "not measured". Judge agreement is future work. 0 model requests.

---

## Phase 10: Optional rows (run only if the budget allows; FR-024a) — FUTURE WORK

> **Future work (2026-11-13)**: out of the reduced scope (spec, "Scope (2026-11-13)"). Kept for a later feature; not built or run now, and `/sp.implement` skips `[FUTURE]` tasks.

- [ ] T052 [FUTURE] [P] [US5] Write failing tests in `tests/test_scope_rule_setting.py`:
  - with `SCOPE_RULE` off, the section, TL;DR and row instructions omit `SCOPE_RULE`, and with it on (the default) they are unchanged;
  - `service.summarize(..., save=False)` and `service.compare(..., save=False)` neither read nor write saved results or unfinished runs;
  - the default `save=True` behaves as before.
- [ ] T053 [FUTURE] [US5] Implement the `SCOPE_RULE` setting in `paperpilot/prompts.py` and `save` in `paperpilot/service.py` so that T052 passes.
- [ ] T054 [FUTURE] [US5] Write failing tests in `tests/evaluation/test_scope.py`:
  - `scope --runs 3` stores each run separately (run index in the key) and never answers a repeat from the cache;
  - a saved rule-on summary or comparison whose recorded configuration matches is reused as one run, and the row says so;
  - claims are judged in batch per part or row;
  - the row reports F2-type verdicts (partly or unsupported on scope) per run and per condition, with no single average, and states the number of runs.
- [ ] T055 [FUTURE] [US5] Implement the `scope` command in `evaluation/answers.py` and `evaluation/__main__.py` so that T054 passes.
- [ ] T056 [FUTURE] [US5] Optional: `answers reasoning-low` then `judge reasoning-low` (`LLM_REASONING_EFFORT=low`). **Planned requests: about 75.** Commit the row.
- [ ] T057 [FUTURE] [US5] Optional: `answers gemma` then `judge gemma` (answered by `google/gemma-4-31b-it:free`, judged by `nvidia/nemotron-3-ultra-550b-a55b:free`). **Planned requests: about 75.** Commit the row.
- [ ] T058 [FUTURE] [US5] Optional: `scope --runs 3` on the LoRA and BERT summaries and the BERT–RAG comparison, rule on and off. **Planned requests: up to about 190**: 3 runs × 2 conditions × 16 parts or rows to generate (96), plus as many to judge (96), less up to 10 reused rule-on outputs. Commit the row.
- [ ] T059 [FUTURE] [US5] After any optional row: `python -m evaluation report` (0 requests); **HUMAN** writes its takeaway; commit.

---

## Phase 11: Polish

- [ ] T060 [P] Add an "Evaluation" section to `docs/known-limitations.md`, and update research R3 of Feature 4 if the scope rule was measured. The section covers:
  - the self-written set of 12 questions;
  - that answer quality, the judge and calibration are not measured yet (future work);
  - the untested larger rerankers;
  - the gate left on vector scores.
- [ ] T061 Run the quickstart offline steps (`check`, `retrieval`, `report`, `pytest`); fix any drift; record Checkpoint 11's results and every real request total in the PHR.

---

## Dependencies & Execution Order

- **Setup (T001–T002)** comes first.
- **Foundational (T003–T012)** blocks every story; T003/T005/T007/T009/T011 are parallel test tasks, each followed by its implementation.
- **US1 (T013–T019)** blocks every run, because all metrics need the golden set. **T016 and T018 (HUMAN)** gate T017 and T019.
- **US2 (T020–T031)** needs US1; the reranker, hybrid and prefix pairs (T025–T030) are independent of each other.
- **Report (T048–T051)** can be built any time after T023; **T050 (HUMAN)** gates T051.
- **Future work (T032–T047, T052–T059)**: not in the reduced scope. When resumed: the best rule needs T031; US6 comes before any real request; US4 needs US6 and T041; US3 needs US4 and US6.

## Parallel Example: Foundational and retrieval tests

```text
T003 tests/test_config_eval.py   T005 tests/test_llm_model_arg.py   T007 tests/test_ask_retrieve.py
T009 tests/evaluation/test_eval_store.py   T011 tests/evaluation/test_experiments.py
T025 tests/evaluation/test_rerank.py   T027 tests/evaluation/test_hybrid.py   T029 tests/test_embed_prefix.py
```

## Request plan (real model requests only)

| Task | Planned | Days at 40 a day |
|---|---|---|
| T043 calibration | one per item, at least 20 (expected 25–35) | 1 |
| T046 baseline answers and judge | about 75 | 2 |
| T047 winner answers and judge | about 75, or 0 if the baseline wins | 2 |
| **Required** | **about 125–185** | **3–5** |
| T056 reasoning effort (optional) | about 75 | 2 |
| T057 second model (optional) | about 75 | 2 |
| T058 scope rule (optional) | up to about 190 | 5 |

**Reduced scope (2026-11-13): 0 requests.** Every task above is future work; every in-scope task makes 0 requests. Each real task prints its exact plan before sending anything.

## Implementation Strategy

1. **MVP**: Setup, Foundational and US1, giving a validated golden set.
2. **Free results**: US2, giving five retrieval rows at no cost, enough for two experiments with
   conclusions once T050's takeaways are written.
3. **Report**: the results table and README block, answer columns "not measured" (Checkpoint 11, reduced).
4. **Future work** (2026-11-13): the best rule, US6, US4's calibration, US3 and the optional rows.

## Notes

- Tasks marked HUMAN are not marked [X] by Claude Code.
- A test task's commit may hold failing tests; its implementation task's commit must pass them.
- Never commit `data/eval/`, PDFs or paper text in `eval/results/`.
