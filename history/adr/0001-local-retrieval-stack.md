# ADR-0001: Local Retrieval Stack

> **Scope**: Document decision clusters, not individual technology choices. Group related decisions that work together (e.g., "Frontend Stack" not separate ADRs for framework, styling, deployment).

- **Status:** Accepted
- **Date:** 2026-10-23
- **Feature:** 001-pdf-ingest-search
- **Context:** PaperPilot must turn research-paper PDFs into a searchable library and return
  passages ranked by meaning, with title, section and page for later citations. The
  constitution requires plain Python (no LangChain), local embeddings with
  `BAAI/bge-small-en-v1.5`, a persistent ChromaDB store, Windows support, and simple,
  explainable code. Targets: add a paper in under 60 s on a laptop CPU, search in under 2 s
  for 5–20 papers, scores in 0–1. Every later feature (answers, citations, eval harness)
  retrieves through this stack.

## Decision

Adopt one integrated, fully local retrieval stack:

- **PDF extraction**: PyMuPDF `page.get_text("blocks", sort=True)`, text blocks only, then a
  band-based re-sort per page: blocks wider than 60% of the page split it into bands; within
  each band, left-column blocks then right-column blocks (column by block left edge vs page
  midpoint), then the wide block. Blocks under 25 characters are
  dropped unless their first line is a heading.
- **Embeddings**: sentence-transformers running `BAAI/bge-small-en-v1.5` on CPU,
  `normalize_embeddings=True`, `batch_size=32`, loaded lazily once per process. Queries get
  the prefix `"Represent this sentence for searching relevant passages: "`; passages get none.
- **Vector store**: `chromadb.PersistentClient` at `LIBRARY_DIR`, telemetry disabled, a single
  collection `passages` with `hnsw:space=cosine`; paper-level fields stored on each passage.
- **Scoring and filtering**: score = `clamp(1 − cosine distance, 0, 1)`; no `where` clause when
  unfiltered, `{"paper_id": {"$in": ids}}` when filtered; `n_results = min(k, count)`.
- **Write consistency**: embed everything in memory, then one `upsert` per paper; on write
  error, delete that paper's passages and re-raise.
- **Ownership**: only `store.py` touches the model and ChromaDB; `library.py` is the public
  entry point.

## Consequences

### Positive

- Zero running cost and no paper text sent to third parties; works offline after the one-time
  model download.
- Small model (384 dimensions, ~130 MB) keeps adds well inside the 60 s target on CPU.
- ChromaDB persists on disk with no server to run, so restarts need no re-embedding.
- One collection keeps listing, filtering, delete and duplicate checks to simple metadata
  queries; the whole stack fits in a few short modules that are easy to explain.
- Column-aware ordering and the heading exemption fix two failure modes found in planning
  (interleaved columns, dropped headings).

### Negative

- sentence-transformers pulls in torch: large install, slow first setup on Windows.
- bge-small is less accurate than larger or hosted embedding models; absolute scores cluster
  high, so score bands are only a sanity check, not a relevance threshold.
- Band heuristic does not handle unusual layouts (three columns, sidebars) or narrow figures
  inside one column.
- Paper-level metadata is duplicated on every passage; listing scans all metadata (fine for
  tens of papers, not for thousands).
- Upsert is not transactional: a hard crash mid-write can leave a partial paper (documented
  limitation; recovery is delete and re-add).
- Changing the embedding model later requires re-embedding the whole library.

## Alternatives Considered

- **Alternative A — LangChain/LlamaIndex pipeline** (loaders + splitters + vector store
  wrappers): fastest to assemble, but forbidden by the constitution and hides the steps the
  project is meant to make explainable.
- **Alternative B — Hosted embeddings + hosted vector DB** (e.g. Gemini/OpenAI embeddings +
  Pinecone/Qdrant Cloud): better embedding quality, no torch install; rejected for cost/quota
  risk, network dependency, sending paper text off-machine, and violating Principle IV.
- **Alternative C — pypdf/pdfplumber + FAISS + JSON metadata files**: lighter than Chroma, but
  FAISS needs hand-written persistence, metadata filtering and deletes; pypdf lacks block
  geometry for column ordering; pdfplumber is slower for the same result.
- **Alternative D — larger local model (bge-base/bge-large)**: better recall, but 3–10× slower
  embedding on CPU, risking the 60 s add target; can be revisited via `EMBED_MODEL`.

## References

- Feature Spec: specs/001-pdf-ingest-search/spec.md
- Implementation Plan: specs/001-pdf-ingest-search/plan.md
- Related ADRs: ADR-0002 (Passage Identity and Chunking Strategy)
- Evaluator Evidence: history/prompts/001-pdf-ingest-search/3-plan-pdf-ingestion-semantic-search.plan.prompt.md;
  research.md R1–R3, R9–R11
