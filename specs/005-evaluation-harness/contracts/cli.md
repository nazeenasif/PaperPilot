# Contract: `python -m evaluation` (Feature 5)

Every command prints its plan first and its request counts last. Exit code 0 means every check
passed; 1 means a failed check or a refused run; 2 means bad arguments.

| Command | Requests | What it does |
|---|---|---|
| `check` | 0 | Validates `eval/golden.json` (research R2) and `eval/experiments.json` (one change each); prints counts per kind. |
| `retrieval [EXPERIMENT ...]` | 0 | Runs retrieval for each experiment (default: every retrieval experiment), writes `eval/results/<name>.json`, prints hit@1/3/6/10 and MRR overall and per kind, the evidence rank per question, and gated not-founds. Builds `data/eval/libraries/prefix/` first if needed. |
| `best` | 0 | Prints the best retrieval configuration by FR-024b, with its figures, or "baseline". |
| `answers EXPERIMENT [--slice N]` | plan | Answers the golden questions through `service.ask` under the experiment's configuration, units cached (research R10). |
| `judge EXPERIMENT [--slice N]` | plan | Judges the stored answers' claims, one request per answer (batch mode). |
| `calibrate import REPORT.md` | 0 | Adds hand-verdict items from a verification report's Verdict column (research R9). |
| `calibrate [--slice N]` | plan | Judges each calibration item, one request per claim, and writes `eval/calibration.md`. |
| `scope [--runs 3] [--slice N]` | plan | Optional scope-rule rows on the fixed set, rule on and off, without saving to the library (FR-025). |
| `report` | 0 | Writes `eval/results.md` and the README block from `eval/results/` and `eval/experiments.json` only. |
| `status` | 0 | Shows each run's progress: planned, done and remaining units, and this day's usage. |

**Plan line** (before any request):

```text
Plan: answers baseline: 40 units, 52 requests in all; 18 done; this session 32 (slice: 40 today less reserve 10 = 30 → 30)
```

**Refusal** (nothing sent): `Not started: 6 requests left today after the reserve of 10, this session needs 30. Requests resume at 05:00 (00:00 UTC).`

**Settings** (read through `paperpilot.config`): `EVAL_JUDGE_MODEL` (default
`google/gemma-4-31b-it:free`), `EVAL_RESERVE` (default 10), `USAGE_DIR` (default `LIBRARY_DIR`),
`EMBED_PREFIX` (default off), `SCOPE_RULE` (default on). Experiments set settings for their own run only.
