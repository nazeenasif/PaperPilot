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
  (axis ticks, legend entries) is not table-like, so it stays in a text passage. Table header
  rows, which are mostly words, may also stay with the surrounding prose. On the Checkpoint 2
  samples about 12 of 15 text passages read cleanly; the rest contain such fragments. The
  goal (SC-003) remains 9 of 10.
- **Figure axis labels can become table passages.** A block of axis ticks such as "5 10 20 30
  40 50 Number of Retrieved Docs" is mostly numbers, so it is classified as a table passage.
  This is harmless for search, but these passages are not real tables.
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
