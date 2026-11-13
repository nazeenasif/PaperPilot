# Quickstart: PDF Ingestion and Semantic Search

Windows, PowerShell, from the repository root.

## 1. Set up

With [uv](https://docs.astral.sh/uv/) (used for this project; a uv venv has no `pip`):

```powershell
uv venv --python 3.12 .venv
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
Copy-Item .env.example .env     # edit values only if you want non-default settings
```

Without uv: `py -3.12 -m venv .venv` (needs Python 3.12, e.g. `winget install Python.Python.3.12`),
activate it, then `pip install -r requirements.txt`.

## 2. Add test papers

Download the 5 test papers from arXiv into `papers/` (gitignored):
Attention Is All You Need (1706.03762), BERT (1810.04805), RAG (2005.11401),
LoRA (2106.09685), Lost in the Middle (2307.03172).

```powershell
New-Item -ItemType Directory -Force papers | Out-Null
foreach ($id in "1706.03762", "1810.04805", "2005.11401", "2106.09685", "2307.03172") {
    curl.exe -sSL --fail -o "papers/$id.pdf" "https://arxiv.org/pdf/$id"
}
```

## 3. Run the checkpoints

```powershell
python scripts/checkpoint_0_settings.py      # settings load and print
python scripts/checkpoint_1_parse.py papers  # titles, sections, no reference text
python scripts/checkpoint_2_chunk.py papers  # coverage, text-passage size, samples
python scripts/checkpoint_3_search.py papers # add, search, filter, duplicates, list/delete
python scripts/checkpoint_3_search.py        # run again with no args: persistence check
```

Each script prints `PASS`/`FAIL` for automated checks, samples for human review, and timings.
The first run downloads the embedding model (~130 MB) once. To start from an empty library,
point `LIBRARY_DIR` at a new folder first, e.g. `$env:LIBRARY_DIR = "data/library-fresh"`.

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
