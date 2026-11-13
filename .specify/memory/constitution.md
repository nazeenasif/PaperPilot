<!--
Sync Impact Report
- Version change: 1.2.0 → 1.3.0 (MINOR: one principle added and two materially expanded;
  backward compatible — no existing module, setting or test changes, and the Python package
  stays the single source of logic)
- Modified principles:
  - I. Plain, Typed Python → I. Plain, Typed Code: the Python rules now cover the engine and
    the backend; frontend code MUST be strict TypeScript and MUST NOT use AI/LLM SDKs.
  - II. Modular Package with a Single LLM Boundary: adds that the FastAPI backend is a thin
    adapter outside the package's module list and the frontend never calls the LLM.
- Added principles:
  - IX. Visible Grounding in a Web Interface (Next.js frontend, FastAPI backend; citations
    open the source PDF at the cited page; progress for long operations; designed failure
    states for not-found, rate limit and timeout).
- Modified sections: Technology Stack and Constraints (Frontend, Backend, Excluded lines);
  Development Workflow and Quality Gates (Constitution Check covers Principles I–IX; UI
  done-criteria).
- Added sections: none
- Removed sections: none
- Roadmap: Streamlit is dropped; terminal scripts remain only for checkpoints and maintenance.
- Templates requiring updates:
  - ✅ .specify/templates/plan-template.md (generic "Constitution Check" gate and an existing
       web-application layout option with frontend/ and backend/; no change)
  - ✅ .specify/templates/spec-template.md (no change)
  - ✅ .specify/templates/tasks-template.md (already lists the web-app path convention; no
       change)
  - ✅ .claude/commands/*.md (no interface references; no change)
  - ✅ specs/001-*, specs/002-* (no UI in scope; their "UI/API are later features" notes stay
       true)
- Follow-up TODOs:
  - The library stores passages only, not the source PDF or its path. Principle IX needs the
    PDF kept on disk (gitignored, under the library directory) so the frontend can open it at
    the cited page; plan this in the API/web feature.
  - The ADR for the web stack (Next.js + FastAPI + PDF viewer) is to be written during that
    feature's plan, not with this amendment.
  - docs/paperpilot-guide.pdf is referenced but not present locally; keep it untracked.
-->

# PaperPilot Constitution

PaperPilot is an AI research-paper assistant built with Retrieval-Augmented Generation (RAG),
implemented by following `docs/paperpilot-guide.pdf`.

## Core Principles

### I. Plain, Typed Code

- The engine and backend MUST target Python 3.12.
- Python code MUST be plain Python; LangChain (and similar orchestration frameworks) MUST NOT
  be used.
- Every public Python function MUST have type hints and a short docstring.
- Frontend code MUST be TypeScript in strict mode; it MUST NOT use AI or LLM SDKs.

Rationale: plain code keeps every RAG step visible, debuggable, and explainable.

### II. Modular Package with a Single LLM Boundary

- The package MUST be split into these modules: `config`, `errors`, `ingest`, `store`,
  `library`, `prompts`, `llm`, `service`.
- Each module has one responsibility: `config` loads settings; `errors` defines the shared
  exception hierarchy; `ingest` reads and chunks papers; `store` embeds and queries the vector
  store; `library` holds paper-library operations (add, search, list, delete); `prompts` builds
  prompts; `llm` calls the model; `service` orchestrates the answer flow and calls `library`.
- Only `llm.py` MAY talk to an LLM. No other module may import an LLM SDK or make LLM calls.
- The FastAPI backend is a thin adapter outside this module list: it MUST translate HTTP
  requests into calls to the package (`service`, `library`) and their results and errors into
  responses, and MUST NOT contain retrieval, prompt, citation or LLM logic.
- The frontend MUST reach the engine only through the backend API; it MUST NOT call the LLM
  or the vector store directly.

Rationale: a single boundary makes the provider swappable and the rest of the code testable
without network access; one engine behind the API means the UI cannot drift from the
grounding rules.

### III. OpenAI-Compatible LLM, Free Tier by Default

- The LLM MUST be a model reached through an OpenAI-compatible API.
- Provider, endpoint and model MUST be selected via the `LLM_PROVIDER`, `LLM_BASE_URL` and
  `LLM_MODEL` environment variables, with the API key in `LLM_API_KEY`, all read through
  `config`.
- Free-tier models MUST be the default; a paid model MAY be used only as an explicit
  configuration choice, never as a code default.
- Switching provider or model MUST require settings changes only, with no code changes.
- Only `llm.py` MAY talk to the LLM (Principle II).

Rationale: free tiers and free models change often; one standard API lets the project move
between providers with a config edit and keeps costs at zero unless someone opts in.

### IV. Local Embeddings, Persistent Vector Store

- Embeddings MUST be computed locally with `BAAI/bge-small-en-v1.5`.
- Vectors MUST be stored in a persistent ChromaDB collection on disk.
- Re-running the app MUST NOT require re-embedding already ingested papers.

Rationale: local embeddings cost nothing and avoid sending paper text to a third party for
indexing; persistence keeps startup fast.

### V. Grounded Answers Only (NON-NEGOTIABLE)

- Every answer MUST be built only from retrieved chunks and MUST cite them with numbered
  citations (e.g. `[1]`, `[2]`) that map to specific retrieved sources.
- Citations in the model output MUST be validated: any citation number that does not
  correspond to a retrieved chunk makes the answer invalid.
- When the context does not support an answer (or validation fails), the system MUST return
  the exact "not found" fallback message, defined once as a constant in `prompts`.
- The system MUST NOT invent facts, sources, or citations.

Rationale: a research assistant is only useful if every claim can be traced to the paper.

### VI. Secrets and Data Hygiene

- Secrets (API keys) MUST come only from a `.env` file loaded by `config`; they MUST NOT be
  hard-coded or logged.
- `.env` MUST be gitignored; an `.env.example` with placeholder values SHOULD be committed.
- PDFs, API keys, and the local ChromaDB data directory MUST NOT be committed.

Rationale: keys leak through history; papers may be copyrighted and are large binaries.

### VII. Testable Checkpoints and Measured Quality

- Every feature MUST end with a testable checkpoint: a command or script whose output proves
  the feature works.
- Pure logic (chunking, prompt building, citation parsing/validation, config parsing) MUST have
  pytest tests that run offline without an LLM or network.
- Answer quality MUST be measured with an eval harness (a fixed question set scored for
  groundedness, citation validity, and correct "not found" behavior); changes to prompts,
  retrieval, or models SHOULD be compared against the previous eval run.

Rationale: RAG regressions are silent; tests catch logic bugs and evals catch quality drift.

### VIII. Simplicity and Small Commits

- Prefer the simplest solution that can be explained in a few sentences over clever ones.
- New dependencies or abstractions MUST be justified by a current need, not a future one.
- Commits MUST be small and meaningful: one logical change per commit with a descriptive
  message.

Rationale: the project is a learning-friendly, explainable codebase; small steps keep it so.

### IX. Visible Grounding in a Web Interface

- PaperPilot's user interface MUST be a web frontend (Next.js, `frontend/`) talking to the
  FastAPI backend; it is not a terminal or Streamlit interface. Terminal scripts remain only
  for checkpoints and maintenance.
- Grounding MUST be visible: every citation `[n]` in an answer MUST be clickable and open the
  source PDF at the cited page, with the paper title, section and page shown.
- Operations that take longer than about a second (ingesting a paper, loading the model,
  generating an answer, rewriting a follow-up) MUST show progress or a working state; the UI
  MUST never appear frozen.
- Every failure state MUST have a designed, friendly presentation that says what happened and
  what the user can do: at least not-found, rate limit (with when to retry), timeout, invalid
  input and unexpected error. Raw stack traces, provider error bodies and API keys MUST NOT
  reach the browser.
- The not-found answer MUST be shown as the exact `NOT_FOUND` sentence from the engine, not
  reworded by the frontend.
- No secret MAY be exposed to the browser (no keys in `NEXT_PUBLIC_*` variables or client
  bundles).

Rationale: a research assistant earns trust when readers can check every claim in one click
and understand every failure; hiding sources or errors undermines Principle V.

## Technology Stack and Constraints

- Language: Python 3.12 (engine and backend); TypeScript (frontend).
- Frontend: Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui, Framer Motion, in
  `frontend/`.
- Backend: FastAPI exposing the `paperpilot` package (the single source of logic).
- LLM: any model behind an OpenAI-compatible API (default: a free-tier model), accessed only
  from `llm.py`.
- Embeddings: `BAAI/bge-small-en-v1.5`, run locally.
- Vector store: ChromaDB, persistent mode.
- Testing: pytest for unit tests; a project eval harness for answer quality.
- Configuration: environment variables via `.env` (`LLM_PROVIDER`, `LLM_BASE_URL`,
  `LLM_MODEL`, `LLM_API_KEY`).
- Excluded: LangChain and comparable RAG frameworks; hosted embedding APIs; paid LLM models as
  a default (allowed only as an explicit configuration choice); Streamlit and terminal user
  interfaces as the product interface; LLM calls from the frontend.

## Development Workflow and Quality Gates

- Work follows Spec-Driven Development: spec → plan → tasks → implement, guided by
  `docs/paperpilot-guide.pdf`.
- A feature is done only when:
  - its testable checkpoint passes;
  - `pytest` passes;
  - the eval harness has been run if the feature affects retrieval, prompts, or the LLM;
  - no secrets, PDFs, or vector-store data are staged;
  - for features with UI, every failure state named in Principle IX is demonstrated in the
    feature's checkpoint.
- Each plan's Constitution Check MUST verify Principles I–IX; any violation MUST be recorded
  in the plan's Complexity Tracking table with a justification.

## Governance

- This constitution supersedes other project practices; where guidance conflicts, it wins.
- Amendments are made through `/sp.constitution`, MUST include a Sync Impact Report, and MUST
  propagate changes to dependent templates in the same commit.
- Versioning follows semantic versioning: MAJOR for removed or redefined principles; MINOR for
  added principles or materially expanded guidance; PATCH for clarifications and wording.
- Every plan and code review MUST check compliance with these principles.
- Runtime agent guidance lives in `CLAUDE.md`.

**Version**: 1.3.0 | **Ratified**: 2026-10-23 | **Last Amended**: 2026-10-24
