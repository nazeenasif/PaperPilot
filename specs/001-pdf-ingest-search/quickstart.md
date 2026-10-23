# Quickstart: PDF Ingestion and Semantic Search

Windows, PowerShell, from the repository root.

## 1. Set up

```powershell
py -3.12 -m venv .venv          # requires Python 3.12 (winget install Python.Python.3.12)
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env     # edit values only if you want non-default settings
```

## 2. Add test papers

Download the 5 test papers from arXiv into `papers/` (gitignored):
Attention Is All You Need (1706.03762), BERT (1810.04805), RAG (2005.11401),
LoRA (2106.09685), Lost in the Middle (2307.03172).

## 3. Run the checkpoints

```powershell
python scripts/checkpoint_0_settings.py      # settings load and print
python scripts/checkpoint_1_parse.py papers  # titles, sections, no reference text
python scripts/checkpoint_2_chunk.py papers  # passage counts, average words, samples
python scripts/checkpoint_3_search.py papers # add, search, filter, duplicate check
python scripts/checkpoint_3_search.py        # run again with no args: persistence check
```

Each script prints `PASS`/`FAIL` for automated checks, samples for human review, and timings.
The first run downloads the embedding model (~130 MB) once.

## 4. Run unit tests

```powershell
pytest
```

No network, model, or PDFs are needed for unit tests.

## 5. Use from Python

```python
from paperpilot.library import add_paper, search, list_papers, delete_paper

add_paper("papers/1706.03762.pdf")
for r in search("what dataset was used for evaluation?"):
    print(r.score, r.title, r.section, r.page)
```
