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
FRONTEND_ORIGINS=http://127.0.0.1:3000,http://localhost:3000   # browser origins the API accepts
```

`frontend/.env.local` (not secret, no keys): `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`.

## 2. Run (two terminals; both bind to 127.0.0.1 only)

```powershell
python -m api                   # same as: uvicorn api.main:app --host 127.0.0.1 --port 8000
cd frontend; npm run dev        # runs: next dev --hostname 127.0.0.1 --port 3000
```

Open **http://127.0.0.1:3000** (or `http://localhost:3000`; both are allowed origins). The app
shows "Getting ready" for ~20–30 s while the embedding model loads, then the Ask screen.

First time with a library filled before this feature: open **Library** and drop the five files
from `papers/`; each shows a **Mapping highlights** step and then reports **PDF attached** (no
embedding); citations can then open the PDFs with exact highlights. Files whose PDF is already
stored report **Already in your library** instead. If a paper reports that highlights are
unavailable, its card and its citations offer **Re-process for exact highlights**.

## 3. Tests (offline; never call the model)

```powershell
pytest                                   # engine + api/ tests with fake LLM and embedder
npm --prefix frontend run typecheck      # tsc --noEmit
npm --prefix frontend test               # Vitest + Testing Library
npm --prefix frontend run test:e2e       # Playwright against a fake backend, desktop and 375 px
```

The Playwright run starts `npm run dev` itself unless a dev server is already on port 3000. It
covers every story at desktop and phone width, sideways scrolling, a keyboard-only pass, the
answer reveal (within 500 ms) and reduced motion.

## 4. Checkpoint 6 (real run against the running API)

```powershell
python scripts/usage.py                         # today's requests first (no model request)
python scripts/checkpoint_6_web.py              # all parts: plan 4 model requests, cap 8
python scripts/checkpoint_6_web.py scope        # one part (here: 3 requests)
python scripts/checkpoint_6_web.py states       # every failure state, scripted model, 0 requests
python scripts/checkpoint_6_web.py library --new-pdf PATH   # also add (then delete) a new paper
python scripts/checkpoint_6_geometry.py         # exact-highlight coverage of papers/, 0 requests
```

Parts: `boundary` (0), `ask` (1), `viewer` (0), `library` (0), `scope` (3; it reuses part `ask`'s
answer as the follow-up's history), `states` (0, in-process; needs no server), `usage` (0) and
`secrets` (0; runs `npm --prefix frontend run build`, so run it last). The script prints its
request plan per part and fails on unplanned requests or totals above twice the plan (Feature 2
budget rule). Today's usage is also in the app's header ("Requests today 34 / 50") and at
`GET http://127.0.0.1:8000/api/usage`.

## 5. Manual checks

The Playwright run and checkpoint part `boundary` automate these; they remain worth a look by
hand after visual changes.

- Narrow the browser to 375 px: no horizontal scrolling; library panel and source viewer open
  as overlays.
- Tab through the Ask screen: every chip, checkbox and button is reachable with a visible focus
  ring; Enter/Space open a citation; Escape closes the viewer.
- Set the OS to reduce motion: answers appear at once.
- `netstat -ano | findstr ":8000 :3000"` shows only `127.0.0.1` listeners.
