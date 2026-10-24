# Quickstart: PaperPilot Web App

Windows, repo root, Python venv active, Node 24 (≥ 20.9). Features 1–2 set up (`.env` with
`LLM_*` settings; library populated).

## 1. Install

```powershell
uv pip install -r requirements.txt     # adds fastapi, python-multipart (pinned)
cd frontend; npm ci; cd ..             # exact versions from package-lock.json
npx --prefix frontend playwright install chromium   # once, for the smoke test
```

Optional settings in `.env`:

```text
DAILY_REQUEST_LIMIT=50                       # replaced by the provider's figure when known
FRONTEND_ORIGIN=http://127.0.0.1:3000        # the only origin the API accepts
```

`frontend/.env.local` (not secret, no keys): `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`.

## 2. Run (two terminals; both bind to 127.0.0.1 only)

```powershell
uvicorn api.main:app --host 127.0.0.1 --port 8000
cd frontend; npm run dev        # runs: next dev --hostname 127.0.0.1 --port 3000
```

Open **http://127.0.0.1:3000** (not `localhost:3000`, which is a different origin). The app
shows "Getting ready" for ~20–30 s while the embedding model loads, then the Ask screen.

First time with the existing library: open **Library** and drop the five files from `papers/`;
each shows a **Mapping highlights** step and then reports **PDF attached** (no embedding);
citations can then open the PDFs with exact highlights. If a paper reports that highlights are
unavailable, its citations offer **Re-process paper for exact highlights**.

## 3. Tests (offline; never call the model)

```powershell
pytest                                   # engine + api/ tests with fake LLM and embedder
cd frontend; npm test                    # Vitest + Testing Library
cd frontend; npm run test:e2e            # Playwright smoke against a fake backend
```

## 4. Checkpoint 6 (real run against the running API)

```powershell
python scripts/checkpoint_6_web.py              # all parts; prints planned requests + retries
python scripts/checkpoint_6_web.py --simulate   # failure states with the fake LLM, 0 requests
```

The script prints its request plan per part and fails on unplanned requests or totals above
twice the plan (Feature 2 budget rule). Check today's usage first in the app's header
("Requests today 34 / 50") or `GET http://127.0.0.1:8000/api/usage`.

## 5. Manual checks

- Narrow the browser to 375 px: no horizontal scrolling; library panel and source viewer open
  as overlays.
- Tab through the Ask screen: every chip, checkbox and button is reachable with a visible focus
  ring; Enter/Space open a citation; Escape closes the viewer.
- Set the OS to reduce motion: answers appear at once.
- `netstat -ano | findstr ":8000 :3000"` shows only `127.0.0.1` listeners.
