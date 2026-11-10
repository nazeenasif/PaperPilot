# Quickstart: Summaries and Comparison (Feature 4)

Builds on Feature 3's quickstart (`specs/003-web-app/quickstart.md`): same install, `.env`, and
both servers on 127.0.0.1. No new dependencies.

## 1. Run

```powershell
python -m api
cd frontend; npm run dev
```

Open http://127.0.0.1:3000. The header has four tabs: **Ask · Library · Summarize · Compare**.

- **Summarize**: pick a paper (or choose Summarize on its Library card). A saved summary opens at
  once ("reopening cost 0 requests"); otherwise the button shows "uses 6 requests · N left today".
- **Compare**: choose 2–4 papers and the aspects; the button shows "uses K requests, 1 per aspect".

Saved results live in `<LIBRARY_DIR>/results.sqlite3` and disappear when their paper is deleted.
Re-processing a paper or changing `LLM_MODEL` keeps them readable, marked as earlier; a full regeneration
replaces them.

## 2. Tests (offline; never call the model)

```powershell
pytest                                   # engine + API with scripted model replies
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run test:e2e       # Summary and Compare screens, desktop and 375 px
```

## 3. Checkpoint 7 (real requests; plan 10, cap 20)

```powershell
python scripts/usage.py                              # at least 10 requests left
python scripts/checkpoint_7_summaries.py             # all parts but retry
python scripts/checkpoint_7_summaries.py states      # scripted per-part states only, 0 requests
```

Parts: `summary` (LoRA, 6), `reopen` (0), `compare` (BERT vs RAG on Method, Datasets, Results; 3),
`not-reported` (BERT vs RAG on Limitations; 1), `states` (0). `retry` (Results and the TL;DR of the
saved LoRA summary; 2) runs only when named. The script prints the plan first,
then every claim with paper, section, page and passage excerpt, and writes them to
`docs/verification/checkpoint-7-<date>.md` for the hand check: fill **Verdict** for at least five
claims from the summary and five from the comparison, and **Fault** (retrieval or model) for any
wrong one, then commit the file.
