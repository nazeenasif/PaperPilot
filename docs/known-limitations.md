# Known Limitations

PaperPilot reads research papers with simple, explainable rules rather than layout models
or OCR. These are the cases the rules do not handle, as found on the five test papers
(Attention, BERT, RAG, LoRA, Lost in the Middle). Design decisions behind each rule are in
`specs/001-pdf-ingest-search/research.md`.

## Input PDFs

- **Scanned (image-only) PDFs are not supported.** There is no OCR. A PDF without extractable
  text is rejected with a clear "no extractable text" error and nothing is stored.
- **Revised versions of a paper are separate papers.** A paper's ID comes from its file
  content, so a new arXiv version (different bytes) gets a new ID and both versions stay in
  the library. Delete the old version yourself.

## Reading order

- **Only one- and two-column layouts are handled.** Blocks wider than 60% of the page split
  it into bands; inside a band the left column is read before the right. Three-column pages,
  sidebars, and narrow figures inside one column are not handled specially and can be read
  out of order.

## Titles

- **Titles are heuristic.** When the PDF metadata has no usable title (all five test papers),
  the largest text on page 1 is used. A large banner or logo text of three or more words
  would win, and a title whose lines differ clearly in font size is cut to its largest part.

## Headings and sections

- **Heading detection is pattern-based.** Standard headings (Abstract, Introduction, Methods,
  …) and numbered top-level headings ("3 Model Architecture") are recognised. Unnumbered
  non-standard headings are missed, so their text stays in the previous section.
- **A numbered line can be mistaken for a heading.** A short capitalised line such as
  "4 Results Overview" in the right place in the sequence looks exactly like a heading.
- **The sequence guard can skip headings.** A numbered heading must be greater than the
  previous one and at most 2 higher, so after two or more missed headings in a row the next
  ones are rejected.
- **Headings that wrap onto a third line are cut off.** When a numbered heading is long
  enough to wrap, the PDF holds the number, the first title line and the second title line
  as three separate lines (e.g. "3" / "How Well Can Language Models" / "Retrieve From Input
  Contexts?" in *Lost in the Middle*). Only the number and the first title line are joined,
  so the section is labelled "How Well Can Language Models". The second line becomes the
  first text of the section. Passages still get the right section; only the label is short.
- **Appendices are excluded.** Everything from the References (or Bibliography) heading
  onward is dropped, including appendices that follow it.

## Text cleaning

- **Hyphenated compounds at line ends lose their hyphen.** Words split across lines
  ("repre-" / "sentation") are rejoined, but so are real compounds: "representation-" /
  "learning" becomes "representationlearning".
- **Equations are flattened.** Mathematical notation becomes plain text with symbols and
  sub/superscripts run together (e.g. "headi = Attention(QW Q"), which reads poorly.

## Tables and figures

- **Mixed blocks stay in text passages.** Table-like blocks (mostly numbers or symbols) become
  separate table passages, but a PDF block that mixes prose with table rows or figure labels
  (axis ticks, legend entries) is not table-like, so it stays in a text passage. On the Checkpoint
  2 samples about 12 of 15 text passages read cleanly; the rest contain such fragments. The goal
  (SC-003) remains 9 of 10.
- **Table header rows are not always found.** Rows directly above a table in the same column join it,
  and a split table repeats them in every piece. A header block beside the table stays out ("Model &
  Method # Trainable", LoRA Table 2), and a table's split can fall mid-row, so a piece's first row may
  not line up with the repeated header. A last piece under `MIN_CHUNK_WORDS` joins the one before, so a
  table passage can pass the word budget by up to that much.
- **Figure axis labels can become table passages.** A block of axis ticks such as "5 10 20 30
  40 50 Number of Retrieved Docs" is mostly numbers, so it is classified as a table passage.
  This is harmless for search, but these passages are not real tables. A short legend or label
  directly above such a block joins it as if it were a header row.
- **Tables are not structured.** Table passages are rows of text, not cells, so column
  meaning is lost.

## Storage

- **A hard crash during a write can leave a partial paper.** A paper is written in one
  operation, and a failed write is cleaned up, but a power loss or killed process in the
  middle of that write could leave some passages behind. The duplicate check would then treat
  the paper as present. Recovery: delete the paper and add it again.
- **Changing chunk settings changes passage IDs.** Passage IDs are positions within the paper,
  so changing `CHUNK_WORDS`, `CHUNK_OVERLAP` or `MIN_CHUNK_WORDS` changes them. Delete and
  re-add papers after changing these settings.

## Search

- **Scores are a guide, not a threshold.** Similarity scores from the embedding model cluster
  closely (the top 6 results often differ by less than 0.03), so the 0.45–0.8 band in the spec
  is a sanity check only; the ranking matters more than the absolute value.
- **The specific answer passage is not always ranked first.** General passages from the right
  paper can outrank the one passage that holds the answer. A 5-query probe found the answer
  in the top 6 for 3 of 5 queries (`eval/probe_notes.md`). Improving this belongs to the
  evaluation feature.
- **Title-and-author passages can take a retrieval slot without adding content.** A paper's
  "Front Matter" passage may hold only its title, authors, affiliations and arXiv line. It
  matches questions that name the paper's topic, so it can fill one of the top 6 slots while
  giving the model nothing to answer from. Example: for "What is LoRA?" it ranked 5th (0.578),
  ahead of passages that explain the method. Whether to drop such passages, or merge them into
  the next passage, is a question for the evaluation feature, measured against the probe
  baseline.
- **The first search after startup is slower.** Opening the library and loading the embedding
  model are one-time costs (about 1–2 s and 2–8 s); later searches take well under a second.

## Question answering

- **A correct answer can be missed when its passage ranks low (false not-found).** The model
  only sees the top passages (6 by default). If the passage that holds the answer ranks below
  them, the model correctly says "I couldn't find that in the selected papers." even though
  the paper does answer the question. Example: "What are the two pre-training tasks of BERT?"
  filtered to the BERT paper — the Masked LM and Next Sentence Prediction passages rank 13 and
  22 within BERT, so the answer is not-found. Filtering to one paper does not fix this, because
  the problem is ranking inside the paper. Reranking is the top-priority experiment for the
  evaluation feature (`eval/probe_notes.md`).
- **A valid citation does not prove the passage supports the claim.** Validation checks that
  every [n] points to a passage that was provided; it does not check what the passage says.
  Two cases passed it: a correct fact cited to the wrong passage, and a claim from one paper
  section stretched to cover others ("Faithfulness cases" in `eval/probe_notes.md`). Checking
  each claim against its passage is a job for the evaluation feature.
- **The relevance threshold is calibrated for this library.** 0.58 was measured for
  bge-small-en-v1.5 on the 5 test papers with 220/40 chunking (`eval/threshold_calibration.md`).
  It must be recalibrated (`python scripts/calibrate_threshold.py`, no LLM requests) when papers,
  chunking or the embedding model change. At 0.58 one word-level near-miss ("How do electrical
  transformers step down voltage?", 0.588) passes and relies on the model saying not-found.
- **Free models change and can be removed.** The default `:free` model can be rate-limited,
  changed or withdrawn by the provider at any time; checkpoint 4 checks that it is still listed.
  Switching needs only `LLM_MODEL` (or another OpenAI-compatible provider in `.env`).
- **Free-tier limits make repeated runs impractical.** OpenRouter's free models allow 20
  requests per minute and 50 per day (1,000 per day after $10 of lifetime credits). One full
  checkpoint run uses about 16 requests, so repeated runs, and any evaluation run over many
  questions, need credits or another provider.
- **The uncited-sentence warning can be noisy.** Sentences are split with a simple rule, so
  abbreviations such as "et al." or "e.g." can split a sentence in two and report its first half
  as uncited. The warning never rejects an answer.

## Web app

- **Localhost only, with no sign-in.** The API and the frontend listen on 127.0.0.1 only and
  accept requests from `http://127.0.0.1:3000` and `http://localhost:3000`. There is no
  network access from other devices and no user accounts yet.
- **Upload jobs live in memory.** Restarting the API forgets queued and running jobs and their
  rows. The library itself is unaffected: a paper is stored only when its job finishes, so an
  interrupted job leaves nothing behind. Drop the file again to retry.
- **One upload is processed at a time.** Files wait in a queue and are parsed and embedded one
  after another. Questions keep working meanwhile.
- **Highlights depend on the chunk settings.** Highlight layouts match the passages made with
  the current `CHUNK_WORDS`, `CHUNK_OVERLAP` and `MIN_CHUNK_WORDS`. A PDF attached to a paper
  stored with other settings gets no exact highlights until it is re-processed, and
  re-processing gives the paper new passage ids, so citations in earlier answers to that paper
  show "This passage is no longer in your library".
- **The usage count covers this key's free requests on OpenRouter only.** The figure comes from
  OpenRouter's `free_model_daily_requests` for the configured key. With another provider it is
  PaperPilot's own count, which misses requests made with the same key outside PaperPilot.
- **The units of `X-RateLimit-Reset` are not confirmed yet.** It is read as epoch
  milliseconds and trusted only within 48 hours, so a different unit falls back to normal
  retries. Its raw value is logged with every retried 429, but no real 429 has been seen yet.
- **The source viewer shows one page at a time.** Use the page buttons or "Open full PDF" to
  read around a passage; a passage that continues onto the next page says so.

## Summaries and comparison

- **The TL;DR check cannot catch a non-numeric claim attached to a valid citation.** The TL;DR
  is checked in code: a sentence without a citation, a citation to a passage that no verified
  section cites, or a number that does not appear in the sections a sentence cites holds the
  TL;DR back. A sentence whose citations are all valid and which states no number passes even
  if the cited sections do not say it — the F1 pattern in `eval/probe_notes.md`, where a correct
  fact was cited to the wrong passage. Summary sections and comparison cells use the answer
  validator, so they share the same blind spot (see "A valid citation does not prove the passage
  supports the claim" under Question answering). Detecting it is assigned to the evaluation
  feature's faithfulness judge; until then, checkpoint 7 lists every claim with its cited
  passages for a hand check.
- **A real number can be placed against the wrong item.** A section or cell can take a number
  from its cited passage and attach it to the wrong table column or the neighbouring result (F3 in
  `eval/probe_notes.md`: LoRA Table 5, and BERT's SQuAD 2.0 figure given to SWAG). The number check
  passes because the number is in the passage.
- **Free-model JSON rows may need a retry.** A comparison row whose reply is not the expected JSON
  fails on its own ("This row couldn't be read") and can be retried for 1 request. The parser
  tolerates code fences and text around the JSON, but not a broken object.
- **The TL;DR number check can report false positives.** A number must appear in the sections a
  sentence cites in the same written form, so a paraphrase ("ten thousand", "10K" for "10,000",
  a converted unit) holds the TL;DR back although it is right.
- **Earlier results are kept for reading until replaced.** After a re-process, a model change or
  an instructions change, a saved summary or comparison stays readable, marked as earlier. Its
  citations whose passage text changed show the text as cited instead of a highlight, and its
  parts cannot be retried one by one; only a full regeneration replaces it.
- **The plan's maximum can refuse a run that would have needed fewer requests.** A summary plans
  6 and a comparison 1 per aspect, and a run starts only if that many remain today. A section
  below the relevance threshold uses no request, so a run refused at 5 requests left might have
  fitted.
- **A grounded cell can still be off-aspect.** RAG has no Limitations section, so its Limitations
  cell reported broader-impact concerns: supported by the passage, but not what the aspect asks.
