# Research: Evaluation Harness (Feature 5)

Date: 2026-11-11. Every figure here was measured or read today, on this machine where it says so.
Nothing here sent a model request; the reranker timings are local.

## R1. Golden set: one versioned JSON file, papers by arXiv ID, evidence by text

**Decision**: `eval/golden.json`, one object `{"version": int, "questions": [...]}`, committed. Each
question has `id`, `kind` (`single`, `cross`, `near_miss`, `off_topic`, `follow_up`), `question`,
`scope` (`library`, meaning the 5 golden papers, or `paper`, meaning filtered to its paper),
`papers` (arXiv IDs), `expected` (the answer in a sentence, or `"not_found"`), `evidence`
(`[{paper, page, phrase}]`) and, for follow-ups, `turns` (earlier question and answer) and
`standalone` (the follow-up as one question). Known cases carry `known_case` (`F1`, `F2`, `Q2`, `Q4`).

Papers are named by arXiv ID (`1810.04805`), which the library already records, and resolved to the
library's paper ID at run time. A missing paper fails the check and names the question.

**Comments**: full-line `//` comments are allowed and removed before parsing, so the file can hold a
commented example for the researcher, who writes the questions (amended 2026-11-11).

**Versioning**: `version` is bumped by hand when a question changes meaning; the file's SHA-256 is
recorded with every result as well, so an edit without a bump is still detected. A row produced on
another version or hash is shown as measured on an earlier golden set (spec US5 scenario 4).

**Rationale**: JSON needs no new dependency (Principle VIII), validates strictly, and keeps nested
evidence and turns readable. The guide's JSONL works too, but one file with a version field is simpler
to version as a whole. Passage IDs are never stored, so re-chunking cannot invalidate an item (FR-002).

**Alternatives considered**: YAML (allows comments and long multi-line answers, but adds PyYAML for a
file of about 40 items); JSONL as in the guide (no place for a set-level version); passage IDs as
the guide's `paper_id` plus chunk (rejected by the spec).

## R2. Evidence matching: normalised text, hyphen-insensitive, never IDs

**Decision**: `evaluation.golden.normalise(text)` does the same cleaning as ingest (`ingest.clean`:
line-break hyphen joins, whitespace), then Unicode NFKC (so `ﬁ` becomes `fi`, as passages keep PDF
ligatures), lower case, removes hyphens and soft hyphens, and keeps letters, digits and the
characters `% . , ± ×` as tokens separated by single spaces. A passage is relevant when it belongs to an
evidence item's paper and `normalise(phrase)` is a substring of `normalise(passage.text)`.

**Why hyphen-insensitive**: ingest drops a hyphen at a line break even inside a real compound
(`docs/known-limitations.md`, "Hyphenated compounds at line ends lose their hyphen"), so
"pre-training" can be stored as "pretraining". Removing hyphens on both sides makes the two match.
`GPT-3` and `GPT3` then also match, which is harmless for evidence.

**Validator** (`eval check`, 0 requests), failing with the question and phrase named, if:
1. the phrase matches **no stored passage** of its paper (the requirement asked for in planning);
2. the phrase is not on its stated page of the PDF (PyMuPDF text of that page, same normalisation);
3. the set breaks FR-001's composition, a paper is missing, or an item has a field that looks like a
   passage ID (`<12 hex>-<n>`).

A phrase cut by a passage boundary fails rule 1, and the fix is a shorter phrase: matching across two
passages would count a hit that no single retrieved passage supports.

**Rationale**: matching by text keeps the set valid across re-chunking and the prefix experiment's
separate library; checking the page catches a phrase copied from the wrong place.

**Alternatives considered**: fuzzy matching with an edit distance (could count a near-copy that
says something else); matching on the PDF only (a phrase on the page may be dropped by ingest, for
example in an excluded appendix, and retrieval could never find it).

## R3. Retrieval metrics: per kind, 0 requests

**Decision**: for each answerable question the **rank** is the first position at which the top k
holds a relevant passage, or, for `cross`, at which every required paper has one (the position of the
last of them). hit@k is the share with a rank ≤ k; MRR is the mean of 1/rank, 0 when none is found
within the shortlist of 20. Both are reported overall and per `kind`, for k = 1, 3, 6 and 10, with
hit@6 the headline (spec FR-028). Follow-ups use `standalone` (spec FR-003), so retrieval is free.

For `near_miss` and `off_topic` the retrieval run also reports how many would be **gated**: their
top vector score is under `RELEVANCE_THRESHOLD`, so `ask` would answer not-found without a request.
This needs no model and shows the gate's share of correct refusals.

Searches cover the 5 golden papers only (`paper_ids` = those papers, or the one paper for
`scope: paper`), so a sixth paper added to the library, such as the slide deck there today, cannot
move the numbers.

**Rationale**: the guide's definitions, with cross-paper and gated questions made explicit.

## R4. Reranker: `cross-encoder/ms-marco-MiniLM-L6-v2` over the vector top 20

Candidates, read from the Hugging Face API on 2026-11-11 and timed on this machine (Windows, CPU,
2 PyTorch threads, sentence-transformers 6.2.0, torch 2.14.1+cpu). Latency is per question, 20
(question, passage) pairs, batch 8, after one warm-up pass. Ranks are where each put the evidence for
the five probe questions of `eval/probe_notes.md`, with rough evidence phrases. That is indicative
only: five questions, and phrases written for this test.

| Model | Revision | Size | Licence | CPU per question | Evidence ranks (vector: 11, 11, 3, 19, 11) |
|---|---|---|---|---|---|
| cross-encoder/ms-marco-TinyBERT-L2-v2 | 81d1926f67cb | 18 MB | Apache-2.0 | 0.16 s | 10, 6, 3, 3, 1 |
| **cross-encoder/ms-marco-MiniLM-L6-v2** | 233902d25c44 | 91 MB | Apache-2.0 | 2.0 s (max 2.4) | 8, 2, 1, 7, 3 |
| cross-encoder/ms-marco-MiniLM-L12-v2 | 7b0235231ca2 | 133 MB | Apache-2.0 | 5.8 s (max 6.9) | 9, 2, 1, 9, 5 |
| mixedbread-ai/mxbai-rerank-xsmall-v1 | b5c6e9da73ab | 142 MB | Apache-2.0 | not measured: loads in float16 on CPU and did not finish in the time allowed | — |
| BAAI/bge-reranker-base | 2cfc18c9415c | 1,112 MB | MIT | not measured: too large for this machine's free memory (about 3 GB) | — |
| BAAI/bge-reranker-v2-m3 | 953dc6f6f85a | 2,271 MB | Apache-2.0 | not measured, as above | — |
| jinaai/jina-reranker-v2-base-multilingual | 9cfeff2df7d4 | 557 MB | CC-BY-NC-4.0 | excluded: non-commercial licence | — |

**Decision**: the reranking experiment uses **MiniLM-L6-v2 at revision 233902d25c44**: the standard
MS MARCO cross-encoder, Apache-2.0, small, and 2 s a question on this CPU, so a full golden run takes
about 80 s. **TinyBERT-L2-v2** is a second retrieval row at no cost, because it is 12 times faster and,
on the five probes, no worse. Both are one variable from the baseline (the reranker), and the
retrieval rows decide. Models are loaded at the pinned revision; a missing or changed revision fails
the experiment before anything runs (spec edge cases).

**Gate**: reranking only reorders. The relevance gate still uses the top **vector** score of the
shortlist, so `RELEVANCE_THRESHOLD`, calibrated on vector scores, keeps its meaning and is not
recalibrated for cross-encoder logits.

**Note**: `cross-encoder/ms-marco-MiniLM-L-6-v2`, the older name, no longer answers at that path; the
current repository is `ms-marco-MiniLM-L6-v2`.

## R5. Hybrid search: rank-bm25 with reciprocal rank fusion, k = 60

**Decision**: BM25 (`rank-bm25` 0.2.2, `BM25Okapi`, k1 1.5, b 0.75, its defaults) over the same
passages the vector search may return (the same papers and filter). Tokens: lower case, NFKC, kept
whole when joined by `-` or `.` (`gpt-3`, `sst-2`, `v1.1`), so names and versions match exactly. The
two top-20 lists are fused with **reciprocal rank fusion**: score(d) = Σ 1 / (60 + rank of d in each
list); the top k are returned. The gate uses the vector list's top score, as for the reranker.

**Why RRF**: it uses ranks only, so it needs no calibration between cosine similarities (0.45–0.85
here) and BM25 scores (unbounded, query-dependent). **k = 60** is the value of Cormack, Clarke and
Büttcher (SIGIR 2009). It was stable across their collections, so it is used as published rather than
tuned on a 40-question set, which would overfit. With 20-item lists, k = 60 keeps first and twentieth
place within a factor of about 1.3, so agreement between the lists matters more than either one's order.

**rank-bm25**: 0.2.2 (Feb 2022), Apache-2.0, depends only on numpy (installed). It is unmaintained
but about 200 lines, and the only new dependency of this feature, justified by the hybrid
experiment (Principle VIII). It is pinned in `requirements.txt` and imported only by the evaluation.

**Alternatives considered**: weighted score fusion (needs score normalisation and a weight tuned on
the golden set); CombSUM/CombMNZ (the same normalisation problem); writing BM25 by hand (no less code
to review than a pinned, tiny library).

## R6. Title and section prefix: a separate library, the baseline untouched

**Decision**: a setting `EMBED_PREFIX` (default off). When on, a passage is **embedded** as
`"{title}. {section}. {text}"`, while its stored text, citations, highlights and fingerprint stay
exactly the passage text. The experiment re-ingests the 5 PDFs from `papers/` into
`data/eval/libraries/prefix/`, a separate `LIBRARY_DIR`, so the researcher's library and saved results
are never touched (spec FR-008, SC-009). Queries are embedded as before.

**Usage counting** stays shared: a new setting `USAGE_DIR` (default: `LIBRARY_DIR`) points every run's
request counter at the main library's `usage.sqlite3`, so a run on the prefix library still counts
against the one daily limit.

**Alternatives considered**: a second Chroma collection in the main library directory (one
`rm` away from the real library, and the store caches its client per directory); prefixing the stored
text as well (it would change what the model reads and cites, so two things would vary at once).

## R7. Judge: `google/gemma-4-31b-it:free`, structured verdicts, cached

**Free list, verified 2026-11-11** (OpenRouter `GET /api/v1/models`, public, no key): 469 models, 12
free. `google/gemma-4-31b-it:free`: context 262,144, max completion 32,768, supports `reasoning` and
`response_format`, no expiry date. `nvidia/nemotron-3-ultra-550b-a55b:free` (the answerer): context
1,000,000, max completion 65,536. `liquid/lfm-2.5-2.6b:free` and `dots-studio/dots-3-note-preview:free`
expire (2026-11-13, 2026-12-31) and are not used.

**Decision**:
- The judge is **gemma-4-31b-it:free** while nemotron answers, and **nemotron** while gemma answers
  (the second-model row), so neither grades itself (FR-013). Set by `EVAL_JUDGE_MODEL`, read through
  `config`; `llm.generate` gains a `model` argument (default: `LLM_MODEL`), so the judge still goes
  through the only LLM boundary, its retries and the shared counter (Principle II).
- **Input**: only claims and their cited passages, with passage text in `<passage>` tags as data. No
  question, expected answer, other claims' passages or answering model (FR-012, US4 scenario 5).
  Calibration sends one claim per request; experiments send one answer, summary part or comparison
  row per request, each claim listed beside its own passages (FR-012).
- **Rules** stated to the judge: judge only against the passages, not outside knowledge; *supported*
  means every part of the claim is stated or directly implied; *partly* means some part is, but another
  is not, including a claim whose scope (models, datasets, conditions) is wider than the passage's, or a
  number given to a different item than in the passage; *unsupported* means the passages do not say it.
- **Output**: JSON `{"verdicts": [{"claim": n, "verdict": "supported" | "partly" | "unsupported",
  "reason": "..."}]}`, parsed as tolerantly as comparison rows (code fences, text around the JSON).
  A reply that cannot be read, a missing claim or a cut-off is **not judged** for those claims, never
  supported (FR-014, SC-010), and is retried on a later run.
- **Limit**: a task kind `judge` with 8,192 output tokens, reasoning included, as for summaries.
- **Cache key**: SHA-256 of the claim text, its passages' texts in order, the judge model,
  `JUDGE_PROMPT_VERSION` and the mode (single or batch), because a batched claim is read with other
  claims beside it (FR-015).

**Alternatives considered**: nemotron judging itself (self-grading); a smaller free model as judge (the
two 1.7–2.6B Liquid models were judged too weak for scope and number checks); provider JSON mode only
(nemotron does not list `response_format`, and the tolerant parser works for both).

## R8. Claims and answer scoring

**Decision**: claims are the sentences of an answer, summary part or comparison cell, split by
`prompts._sentences` (the validator's rule, with its abbreviation handling). A claim's passages are
the passages its own citations name. An uncited claim is not sent to the judge; it counts as **uncited**
and against faithfulness (FR-011). A not-found answer has no claims.

Per answer: citation validity (`review_reply`'s verdict), correct refusal (`not_found` on a
`near_miss` or `off_topic` question), false not-found (`not_found` on an answerable one), and claim
verdicts. Faithfulness = supported / all claims, with partly, unsupported, uncited and not judged
shown beside it. Correct refusals = refused / expected not-found. Latency = wall time per answer.

## R9. Calibration: hand verdicts from the reports and the probe notes

**Decision**: calibration items are stored in `eval/calibration.json` (committed), each with the
claim, a **snapshot of its passages' text**, the hand verdict, the source and an optional note.
Snapshots keep an item valid after re-chunking (FR-020). Two ways in:

1. `eval calibrate import <report.md>` reads a verification report's table, where the developer
   fills **Verdict** (`correct`, `partly`, `wrong` map to supported, partly, unsupported). Each cited
   excerpt (the first 200 characters) is matched by normalised prefix to a stored passage, and the full
   text is snapshotted. An excerpt that matches nothing is listed and the item skipped, never guessed.
2. Known cases from `eval/probe_notes.md` (F1, F2 ×4, F3 ×3, the off-aspect cell, incomplete
   citations) are written as items by hand, with the passage text copied from the store or the notes.

**Metric**: agreement on the three labels, and on two (supported against not), plus **Cohen's
kappa** for the three labels, and agreement within each hand label. Every disagreement is listed in
`eval/calibration.md` with the claim, passages, hand verdict, judge verdict and reason (FR-021). Below
20 items, or fewer than 8 supported or 8 not supported, the report says **not calibrated** (FR-022).

**Rationale**: kappa corrects for chance, which matters when most hand verdicts share one label. Per-label
agreement shows a judge that is lenient (misses F2) or harsh (rejects good claims), which overall agreement hides.

## R10. Sessions: plan, slice, reserve, resume

**Decision**: a run is a set of **units**: one answer (1 request, or 2 for a follow-up with its rewrite),
one judge request per answer or per calibration claim, and one summary part or comparison row. Before
any request, `eval answers|judge|calibrate` prints the total plan, the units already done (found in
the cache) and this session's plan.
- **Slice**: `--slice N`, or with none, today's remaining requests less the **reserve** (`EVAL_RESERVE`,
  default 10), up to the work left. The session starts only if today's remaining less the reserve
  covers it, and otherwise says when requests resume (FR-018).
- During a session, a unit starts only while the slice and today's remaining less the reserve still
  cover its cost, so retries cannot eat the reserve. A daily limit, long wait or busy model ends the
  session; finished units are already stored (FR-019).
- **Resume**: the next session finds finished units in the cache and plans only the rest, on any day.

## R11. Storage and results

**Decision**:
- **Cache** `data/eval/eval.sqlite3` (gitignored, under `data/`, as it holds passage text): answers by
  configuration hash and question, verdicts by R7's key, run progress. WAL with `BEGIN IMMEDIATE`, as
  the other SQLite files (ADR-0007).
- **Experiments** `eval/experiments.json` (committed): name, `changes` (one setting from the
  baseline, FR-023), whether answers are evaluated, the developer's `takeaway`, and whether the row is optional.
- **Results** `eval/results/<experiment>.json` (committed, no paper text): the full configuration,
  metrics overall and per kind, per-question ranks and outcomes, request counts, and the golden version
  and hash.
- **Configuration recorded**: answer and judge models, reasoning effort, output limits, a hash of each
  instruction (answers have no version number, so their text is hashed) and `SUMMARY_PROMPT_VERSION`,
  `JUDGE_PROMPT_VERSION`, chunk settings, embedding model and prefix, retrieval method with its
  parameters and model revisions, k, shortlist, relevance threshold, the 5 papers' passage fingerprints,
  the golden version and hash, and the git commit.
- **One variable**: a configuration is compared with the baseline's, ignoring derived fields (the
  fingerprints follow from `EMBED_PREFIX`) and the commit; more than one difference refuses the experiment.
- **Report** `eval report`: writes `eval/results.md` (rows, per-kind tables, the calibration summary, the
  set's size and limits) and the same table between `<!-- eval-results:start -->` and
  `<!-- eval-results:end -->` in `README.md`, appending the section if the markers are absent. It reads
  only `eval/results/` and `eval/experiments.json`, so it runs on a fresh clone and twice gives the
  same output (FR-029, SC-008). Unmeasured cells read "not measured"; a row without a takeaway says so.

## R12. Experiments within the engine: small seams, no new defaults

**Decision**: the harness reaches the engine through public functions only, with these small seams:
- `service.ask(..., retrieve=None)`: a function returning passages and the gate score, so reranking and
  hybrid search run through the real answer pipeline (FR-009). The default is today's `library.search`
  with the gate on its top score, so `ask` behaves as before.
- `llm.generate(..., model=None)` (R7); `USAGE_DIR` and `EMBED_PREFIX` settings (R6); a task kind `judge`.
- `service.summarize(..., save=False)` and `service.compare(..., save=False)` for the optional
  scope-rule rows, so the researcher's saved results are never replaced; and a setting `SCOPE_RULE`
  (default on) read where the instructions are built.

Reasoning effort and the second model are existing settings (`LLM_REASONING_EFFORT`, `LLM_MODEL`)
applied for the run. No default changes (FR-026).

**Rationale**: a seam with today's behaviour as its default keeps every existing test meaningful;
experiment code lives in the harness, not in the engine, until a later change adopts a result.
