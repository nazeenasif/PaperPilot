# Quickstart: Evaluation Harness (Feature 5)

Builds on Feature 4's quickstart. One new dependency, `rank-bm25==0.2.2`, for the hybrid experiment.

## 1. Check the golden set (0 requests)

```powershell
python -m evaluation check
```

## 2. Retrieval experiments (0 requests)

```powershell
python -m evaluation retrieval          # baseline, rerank-minilm-l6, rerank-tinybert, hybrid-rrf60, prefix
python -m evaluation best               # the configuration answer evaluation will use (FR-024b)
```

The first `prefix` run builds `data/eval/libraries/prefix/` from `papers/` (a few minutes of local
embedding). The first reranker run downloads its pinned model (91 MB or 18 MB).

## 3. Calibrate the judge (one request per claim)

Fill the **Verdict** column of the verification reports, then:

```powershell
python -m evaluation calibrate import docs/verification/checkpoint-7-2026-11-11.md
python -m evaluation calibrate          # needs ≥ 20 items, ≥ 8 supported and ≥ 8 not
```

## 4. Answer evaluation (spread over days)

```powershell
python -m evaluation status
python -m evaluation answers baseline   # this session: today's remaining less the reserve of 10
python -m evaluation judge baseline
python -m evaluation answers <best> ; python -m evaluation judge <best>
```

Run each again on later days until `status` shows them done. Finished units are never repeated.

## 5. Optional rows, if the budget allows

```powershell
python -m evaluation answers reasoning-low ; python -m evaluation judge reasoning-low
python -m evaluation answers gemma ; python -m evaluation judge gemma
python -m evaluation scope --runs 3
```

## 6. Report (0 requests)

Write each experiment's `takeaway` in `eval/experiments.json`, then:

```powershell
python -m evaluation report             # eval/results.md and the README results block
```

## Tests (offline; never call the model)

```powershell
pytest tests/evaluation
```
