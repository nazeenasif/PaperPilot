<!--
Sync Impact Report
- Version change: 1.1.0 → 1.2.0 (MINOR: Principle III broadened and made more specific;
  backward compatible — Gemini and Groq remain usable through their OpenAI-compatible
  endpoints, and no existing code depends on a vendor SDK)
- Modified principles:
  - III. Swappable Free-Tier LLM Provider → III. OpenAI-Compatible LLM, Free Tier by Default:
    the provider list "Gemini or Groq" is replaced by "any model reached through an
    OpenAI-compatible API", selected by `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL` with the key
    in `LLM_API_KEY`; free-tier models are the default and paid models need an explicit
    configuration choice; the single-boundary rule (`llm.py` only) is restated.
- Modified sections: Technology Stack and Constraints (LLM, Configuration and Excluded lines
  aligned with Principle III).
- Added sections: none
- Removed sections: none
- Templates requiring updates:
  - ✅ .specify/templates/plan-template.md (no provider names referenced; no change)
  - ✅ .specify/templates/spec-template.md (no change)
  - ✅ .specify/templates/tasks-template.md (no change)
  - ✅ .claude/commands/*.md (no provider names referenced; no change)
  - ✅ specs/002-grounded-qa-citations/plan.md (Principle III row now passes; Complexity
       Tracking row for the provider removed)
  - ✅ history/adr/0003-llm-boundary-and-retry-policy.md (amendment noted)
- Follow-up TODOs:
  - docs/paperpilot-guide.pdf is referenced but not present locally; keep it untracked.
-->

# PaperPilot Constitution

PaperPilot is an AI research-paper assistant built with Retrieval-Augmented Generation (RAG),
implemented by following `docs/paperpilot-guide.pdf`.

## Core Principles

### I. Plain, Typed Python

- Code MUST target Python 3.12.
- Code MUST be plain Python; LangChain (and similar orchestration frameworks) MUST NOT be used.
- Every public function MUST have type hints and a short docstring.

Rationale: plain code keeps every RAG step visible, debuggable, and explainable.

### II. Modular Package with a Single LLM Boundary

- The package MUST be split into these modules: `config`, `errors`, `ingest`, `store`,
  `library`, `prompts`, `llm`, `service`.
- Each module has one responsibility: `config` loads settings; `errors` defines the shared
  exception hierarchy; `ingest` reads and chunks papers; `store` embeds and queries the vector
  store; `library` holds paper-library operations (add, search, list, delete); `prompts` builds
  prompts; `llm` calls the model; `service` orchestrates the answer flow and calls `library`.
- Only `llm.py` MAY talk to an LLM. No other module may import an LLM SDK or make LLM calls.

Rationale: a single boundary makes the provider swappable and the rest of the code testable
without network access.

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

## Technology Stack and Constraints

- Language: Python 3.12.
- LLM: any model behind an OpenAI-compatible API (default: a free-tier model), accessed only
  from `llm.py`.
- Embeddings: `BAAI/bge-small-en-v1.5`, run locally.
- Vector store: ChromaDB, persistent mode.
- Testing: pytest for unit tests; a project eval harness for answer quality.
- Configuration: environment variables via `.env` (`LLM_PROVIDER`, `LLM_BASE_URL`,
  `LLM_MODEL`, `LLM_API_KEY`).
- Excluded: LangChain and comparable RAG frameworks; hosted embedding APIs; paid LLM models as
  a default (allowed only as an explicit configuration choice).

## Development Workflow and Quality Gates

- Work follows Spec-Driven Development: spec → plan → tasks → implement, guided by
  `docs/paperpilot-guide.pdf`.
- A feature is done only when:
  - its testable checkpoint passes;
  - `pytest` passes;
  - the eval harness has been run if the feature affects retrieval, prompts, or the LLM;
  - no secrets, PDFs, or vector-store data are staged.
- Each plan's Constitution Check MUST verify Principles I–VIII; any violation MUST be recorded
  in the plan's Complexity Tracking table with a justification.

## Governance

- This constitution supersedes other project practices; where guidance conflicts, it wins.
- Amendments are made through `/sp.constitution`, MUST include a Sync Impact Report, and MUST
  propagate changes to dependent templates in the same commit.
- Versioning follows semantic versioning: MAJOR for removed or redefined principles; MINOR for
  added principles or materially expanded guidance; PATCH for clarifications and wording.
- Every plan and code review MUST check compliance with these principles.
- Runtime agent guidance lives in `CLAUDE.md`.

**Version**: 1.2.0 | **Ratified**: 2026-10-23 | **Last Amended**: 2026-10-24
