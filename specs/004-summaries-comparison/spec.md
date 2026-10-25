# Feature Specification: Paper Summaries and Cross-Paper Comparison

**Feature Branch**: `004-summaries-comparison`
**Created**: 2026-10-25
**Status**: Draft
**Input**: User description: "Feature 4: Paper summaries and cross-paper comparison for PaperPilot
(see docs/paperpilot-guide.pdf, Phase 6), built into the existing web app. Visual style:
docs/design/ (dark cinematic). Every grounding rule from Features 2–3 applies: citations validated
in code, not-found instead of guessing, nothing unverified shown as verified." The full description,
with its five user stories, functional requirements, out-of-scope list and acceptance criteria
(guide Checkpoints 6–7), is recorded in `history/prompts/004-summaries-comparison/`.

## Context

PaperPilot already answers questions from a local paper library with validated citations
(Feature 2), and has a web app with a Library, an Ask screen, a source viewer that opens the PDF at
the cited page with the passage highlighted, designed failure states and a daily request meter
(Feature 3). The free model allows about 50 requests per day, so every model request is visible and
budgeted.

This feature adds two ways to read papers without asking a question: a structured **summary** of
one paper, and a **comparison** table across two to four papers. Both follow the same grounding
rules as answers: every statement is tied to numbered passages, the citations are checked by
PaperPilot (not trusted from the model), anything unsupported is reported as not found, and
nothing unchecked is ever shown as checked.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Summarize a paper with cited sections (Priority: P1)

On a paper's card in the Library the researcher chooses **Summarize**. The app shows what the
summary will cost (for example "Up to 6 model requests · 41 left today") and starts it on
confirmation. Progress appears section by section (for example "Reading method passages",
"Writing method", "Checking method"). The summary shows a short TL;DR and five sections —
**Problem**, **Method**, **Data**, **Results** and **Limitations** — each with its own numbered
citations. Each citation opens the paper's PDF at the cited page with the passage highlighted, as
answers do. A section appears only after its citations have been checked.

**Why this priority**: the summary is the core new capability and the basis for caching
(User Story 2); comparison builds on the same per-part grounding.

**Independent Test**: summarize LoRA; confirm the TL;DR and the five sections appear with
citations, every citation opens the PDF at the right page with the passage highlighted, and the
number of model requests used is no more than the stated cost plus retries.

**Acceptance Scenarios**:

1. **Given** a paper in the library, **When** the researcher chooses Summarize, **Then** the app
   shows the maximum number of model requests the summary will use and today's remaining requests
   before anything is sent, and starts only on confirmation.
2. **Given** a summary in progress, **Then** progress is shown per section, and no section's text
   appears before that section's citations have been checked.
3. **Given** a finished summary, **Then** it shows a TL;DR and the five sections in the fixed
   order Problem, Method, Data, Results, Limitations, each with its own citations to passages of
   that paper only.
4. **Given** a citation in a summary section or in the TL;DR, **When** the researcher opens it,
   **Then** the source viewer opens the paper's PDF at the cited page with the passage highlighted
   (or, where the location cannot be marked, the passage text beside the page, as for answers).
5. **Given** the TL;DR, **Then** it carries citations, and every one of them points to a passage
   cited by one of the summary's checked sections; a TL;DR without citations is not shown.

---

### User Story 2 - Reopen a saved summary at no cost; regenerate on request (Priority: P1)

A summary, once generated, is saved. Opening it again shows it instantly with no model requests,
with a note of when it was generated and with which model. The researcher can choose
**Regenerate**, which shows its cost first and replaces the saved summary when finished. A saved
summary that no longer matches the paper or the configured model is not shown as current.

**Why this priority**: with about 50 free requests a day, a summary that had to be regenerated on
every view would be unusable; reopening for free is part of the summary's basic value.

**Independent Test**: summarize LoRA, reload the app, open the LoRA summary again and confirm it
appears at once and the day's request count is unchanged; then re-process LoRA (or change the
configured model) and confirm the old summary is no longer offered as current.

**Acceptance Scenarios**:

1. **Given** a saved summary, **When** the researcher opens it (also after a restart of the app),
   **Then** it appears immediately and today's request count does not change.
2. **Given** a saved summary, **When** the researcher chooses Regenerate and confirms the stated
   cost, **Then** a new summary is generated and replaces the saved one only when it has finished.
3. **Given** a saved summary, **When** the paper is re-processed, deleted, or the configured model
   changes, **Then** the saved summary is no longer shown as current; the researcher is told why
   and can generate a new one.
4. **Given** a saved summary with a part that failed for a temporary reason (for example the model
   was busy), **When** the researcher chooses to retry that part, **Then** only that part (and the
   TL;DR, which depends on it) is generated again, with the cost shown first.

---

### User Story 3 - Compare 2–4 papers in a cited table (Priority: P2)

On a **Compare** screen the researcher selects two to four papers and the aspects to compare
(by default Problem, Method, Datasets, Results and Limitations). The app shows the cost and starts
on confirmation. The result is a table with one column per paper and one row per aspect; every
cell carries its own citations to passages of that cell's paper, and each citation opens the PDF
with the highlight. Every paper gets the same share of retrieved passages for every aspect, so a
long paper cannot crowd out a short one. A comparison, once generated, is saved and reopens at no
cost, like a summary.

**Why this priority**: comparison reuses the per-part grounding of summaries and is the second
half of the guide's Phase 6; it depends on User Story 1's grounding rules being in place.

**Independent Test**: compare BERT and RAG on Method, Datasets and Results; confirm a 3 × 2 table
in which every cell's citations point only to that cell's paper and open the PDF correctly, and the
model requests used do not exceed the stated cost plus retries.

**Acceptance Scenarios**:

1. **Given** the Compare screen, **When** fewer than 2 or more than 4 papers are selected, or no
   aspect is selected, **Then** the comparison cannot be started and the app says why.
2. **Given** a running comparison, **Then** progress is shown per aspect, and no cell's text
   appears before that cell's citations have been checked.
3. **Given** a finished comparison, **Then** each cell cites only passages from its own paper; a
   citation to another paper's passage in a cell counts as invalid for that cell.
4. **Given** a saved comparison of the same papers and aspects (in any order), **When** it is
   opened again, **Then** it appears immediately with no model requests, and Regenerate works as
   for summaries.

---

### User Story 4 - Unsupported parts say "Not reported" while the rest stays visible (Priority: P1)

When the retrieved passages do not support a summary section or a comparison cell, that part reads
**"Not reported in the retrieved passages"** instead of an invented value. When the model's text
for a part cites passages it was not given (or another paper's passages, in a comparison cell),
that part is held back with a warning and its unverified text can be viewed, clearly labelled as
not verified, as for answers. In every case only that part is affected; all other parts are shown.

**Why this priority**: this is the grounding rule (constitution Principle V) applied to the new
outputs; without it a summary or table could present invented facts as checked.

**Independent Test**: with scripted model replies, produce a summary in which one section has no
citations and another cites a passage that was not provided; confirm the first reads "Not reported
in the retrieved passages", the second is held back with a viewable unverified text, and the other
sections are shown normally. In a real comparison, confirm a cell the paper does not support reads
"Not reported in the retrieved passages".

**Acceptance Scenarios**:

1. **Given** a summary section or comparison cell whose model text has no citations, or for which
   no sufficiently relevant passage was retrieved, **Then** that part shows "Not reported in the
   retrieved passages" and no model-written text for it is shown as checked.
2. **Given** a part whose model text cites a passage number that was not provided for it, **Then**
   that part is held back with a warning that names the invalid citation, and "View the unverified
   text" reveals the original text labelled as not verified, with the invalid numbers marked.
3. **Given** any part that is not reported, held back or failed, **Then** every other part of the
   same summary or comparison is still shown with its citations.
4. **Given** a part whose output was cut off by the model's output limit, **Then** that part shows
   a designed "cut off" state with the option to retry it; it never shows truncated text.
5. **Given** a summary whose five sections are all not reported, held back or failed, **Then** no
   TL;DR is generated (no request is spent on it) and the TL;DR reads "Not reported in the
   retrieved passages".

---

### User Story 5 - Known cost before starting; daily limit and busy states as for questions (Priority: P2)

Before a summary, comparison, regeneration or part retry starts, the app shows how many model
requests it will use at most and how many remain today. If the remaining requests are fewer than
the stated cost, the run is not started and the daily-limit state explains when requests resume;
saved summaries and comparisons stay available. While running, the busy-and-retrying countdown,
the long-wait ("try again at …") state and the daily-limit state behave as they do for questions,
per part. The request meter updates as requests are spent.

**Why this priority**: the free tier makes cost visible by necessity; the states already exist and
must cover the new, longer-running tasks.

**Independent Test**: with the daily usage set close to the limit, confirm Summarize shows the cost
and refuses to start when fewer requests remain than it needs, with no request sent; with a
simulated rate limit, confirm the countdown appears for the part being generated and the summary
completes when the retry succeeds.

**Acceptance Scenarios**:

1. **Given** any summary, comparison, regeneration or part retry, **Then** its maximum request
   cost is shown before it starts, and the requests it actually uses (first attempts) never exceed
   that number; retries are counted and reported separately, as for questions.
2. **Given** today's remaining requests are fewer than the stated cost, **When** the researcher
   tries to start, **Then** nothing is sent, and the daily-limit state shows when requests resume.
3. **Given** a part is waiting for a retry, **Then** the busy countdown with "attempt N of M" is
   shown for that part, and the remaining parts continue afterwards.
4. **Given** the provider reports the daily limit or a long wait during a run, **Then** no further
   requests are sent for that run, completed parts are kept and saved, and the unfinished parts
   show the daily-limit or "try again at …" state with the option to retry them later.
5. **Given** a question, summary or comparison is running, **When** the researcher starts another
   one, **Then** it is refused with the existing "busy" state (one model task at a time).

---

### Edge Cases

- **A paper with no passages for a facet** (for example no limitations discussion): that section
  reads "Not reported in the retrieved passages" and no model request is spent on it; the stated
  cost was a maximum, so the run simply uses fewer requests.
- **Passages shared between facets**: the same passage keeps one number within a summary or
  comparison, wherever it is cited.
- **The same paper selected twice for comparison**, or a paper deleted while its comparison is
  open: duplicates are not allowed; a comparison whose paper was deleted is no longer current.
- **A paper deleted while a summary of it is running**: the run ends with the "paper no longer in
  your library" state; nothing is saved.
- **Model reply in an unexpected shape** (for example a table with missing rows or extra papers):
  each expected part is checked on its own; a missing part reads "Not reported in the retrieved
  passages", extra content is ignored and never shown.
- **The configured model is changed while a summary is saved**: the saved summary stays readable
  only as "generated with an earlier model — regenerate for a current summary", never as current.
- **Very short papers** (one or two sections): facets without relevant passages are not reported;
  the TL;DR is generated from whatever sections were verified.
- **Comparison aspects that the papers describe very differently** (one paper's "data" is a
  benchmark, another's a corpus): each cell reflects only its own paper's passages.

## Requirements *(mandatory)*

### Functional Requirements

**Summaries (User Stories 1, 2, 4)**

- **FR-001**: The researcher MUST be able to open or start a summary of any paper in the library
  from its card in the Library and from the Summarize tab, which lists the papers with their saved
  summaries.
- **FR-002**: A summary MUST consist of a TL;DR and five sections in this order: Problem, Method,
  Data, Results, Limitations.
- **FR-003**: Summaries MUST be query-focused: for each section, passages MUST be retrieved from
  that paper only with a query for that facet, and the section MUST be generated from those
  passages alone, with one model request per section that has relevant passages.
- **FR-004**: Passages MUST be numbered once per summary; the same passage MUST keep the same number
  wherever it appears.
- **FR-005**: The TL;DR MUST be generated only from the sections that passed validation, MUST cite
  passages, and every TL;DR citation MUST be a passage cited by one of those sections; a TL;DR
  with invalid or missing citations MUST be held back or reported as not reported under the same
  rules as sections.
- **FR-006**: Summarizing every passage of a paper and then combining the partial summaries
  ("map-reduce") is out of scope; it is recorded as the rejected alternative, because its request
  cost grows with paper length (tens of requests per paper) and it does not keep each statement tied
  to a small set of citable passages.

**Comparisons (User Stories 3, 4)**

- **FR-007**: The researcher MUST be able to compare 2 to 4 different papers on a chosen set of
  one or more aspects, selected from a fixed list: Problem, Method, Datasets, Results,
  Limitations (all selected by default). Aspects cannot be typed in; each has a retrieval query and
  instruction written and tested by PaperPilot.
- **FR-008**: For each aspect, passages MUST be retrieved per paper separately with the same number
  of passages per paper, so that no paper dominates; passages MUST be de-duplicated and numbered
  once per comparison.
- **FR-009**: The comparison MUST be generated as a table with one row per aspect and one cell per
  paper, citations inside cells, with one model request per aspect (one row at a time). A
  comparison therefore costs at most as many requests as it has aspects; each row's output stays
  short enough for the output budget, progress is shown per row, and a failed or cut-off row can be
  retried on its own.
- **FR-010**: Each cell MUST be validated on its own: a citation counts as valid only if it refers
  to a passage provided for that cell's paper and aspect.

**Validation and display (all stories)**

- **FR-011**: Every summary section, the TL;DR and every comparison cell (each a "part") MUST be
  validated independently: a part with invalid citations MUST be held back with a warning and its
  unverified text viewable only when clearly labelled as not verified; a part with no citations, or
  for which no relevant passages were retrieved, MUST read "Not reported in the retrieved passages";
  the remaining parts MUST stay visible.
- **FR-012**: No part's text MAY be shown before its validation has finished; progress MUST be
  shown per section or aspect while the run is in progress, in the style of question progress.
- **FR-013**: Every citation in a summary or comparison MUST open the source viewer at the cited
  page with the passage highlighted, exactly as for answers (Feature 3), including the "location
  not marked" fallback.
- **FR-014**: A part whose model output was cut off by the output limit (reasoning tokens included)
  MUST be treated as failed for that part, shown with a designed "cut off" state and a retry
  option; truncated text MUST NOT be shown. Prompts and requested output lengths MUST be sized so
  that a normal part fits the model's output budget.
- **FR-015**: Summary and comparison screens MUST follow the visual reference in `docs/design/`
  (dark cinematic; teal for verified elements, amber for citations), MUST work at 375 px width
  without horizontal scrolling and MUST be usable with the keyboard alone, as Feature 3's screens.

**Saving and reuse (User Story 2)**

- **FR-016**: A finished summary MUST be saved per paper, and a finished comparison per set of
  papers and set of aspects (independent of selection order), so that reopening shows it with zero
  model requests, also after the app restarts.
- **FR-017**: A saved summary or comparison MUST NOT be shown as current when any of its papers has
  been re-processed or deleted, when the configured model has changed, or when PaperPilot's
  summary or comparison instructions have changed; the researcher MUST be told why and offered a new
  generation.
- **FR-018**: Saved results MUST show when they were generated and with which model.
- **FR-019**: Regenerate MUST show its cost first and MUST replace the saved result only after the
  new one has finished; a failed regeneration MUST leave the saved result as it was.
- **FR-020**: Completed parts of a run MUST be saved even when other parts failed for a temporary
  reason (busy, long wait, daily limit, cut off); the researcher MUST be able to retry only the
  failed parts, and the TL;DR MUST be regenerated when any section it depends on changes.

**Cost and limits (User Story 5)**

- **FR-021**: Before any summary, comparison, regeneration or part retry starts, the app MUST show
  its maximum number of model requests (first attempts) and today's remaining requests.
- **FR-022**: Every model request of a summary or comparison MUST be counted by the shared daily
  request counter (Feature 3); the first attempts MUST NOT exceed the stated maximum, and retries
  MUST be reported separately.
- **FR-023**: A run MUST NOT start when today's remaining requests are fewer than its stated
  maximum; the daily-limit state MUST be shown instead, and saved results stay available.
- **FR-024**: The busy-and-retrying, long-wait and daily-limit states MUST behave per part as they
  do for questions; when the provider reports the daily limit or a long wait, no further requests
  MUST be sent for that run.
- **FR-025**: Only one model task (question, summary or comparison) MAY run at a time; another
  start MUST be refused with the existing busy state.

**Checkpoint (guide Checkpoints 6–7)**

- **FR-026**: The feature MUST end with a checkpoint that generates a summary of LoRA and a
  comparison of BERT and RAG on Method, Datasets and Results, checks that every citation is valid,
  reopens the LoRA summary and confirms 0 model requests, demonstrates a "Not reported in the
  retrieved passages" cell, and prints its planned and actual model requests (first attempts and
  retries) before and after running.
- **FR-027**: The checkpoint MUST print, for each claim in the LoRA summary and the BERT–RAG
  comparison, the cited paper, page and passage, so that at least five claims from each can be
  verified by hand against the PDFs; the results MUST be recorded, noting for every wrong claim
  whether retrieval (wrong or missing passages) or the model (misread passage) was at fault.

### Key Entities

- **Summary**: one paper's TL;DR and five sections, plus its numbered passages, when it was
  generated, the model used, and what it was generated against (the paper's current passages and
  PaperPilot's summary instructions), so that a stale summary can be recognised.
- **Comparison**: a table for 2–4 papers and a set of aspects, with numbered passages per cell, the
  generation time and model, and what it was generated against.
- **Part**: one summary section, the TL;DR or one comparison cell; its state is one of verified
  (text with valid citations), not reported, held back (with unverified text and invalid
  citations), or failed (cut off, busy, long wait, daily limit), plus the requests it used.
- **Facet / Aspect**: a named topic that drives retrieval and generation for a part (summary
  facets: Problem, Method, Data, Results, Limitations; comparison aspects: chosen per comparison).
- **Request plan**: the maximum number of model requests a run will make, shown before it starts
  and compared with the requests actually used afterwards.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the checkpoint, the LoRA summary and the BERT–RAG comparison (Method, Datasets,
  Results) are generated with 100% of shown citations valid and every citation opening its paper's
  PDF at the cited page.
- **SC-002**: At least five claims from the LoRA summary and five from the BERT–RAG comparison are
  verified by hand against the PDFs and recorded; for every claim found wrong, the record states
  whether retrieval or the model was at fault.
- **SC-003**: Reopening the LoRA summary, also after restarting the app, shows it within 1 second
  and changes today's request count by 0.
- **SC-004**: In the checkpoint, at least one comparison cell that the paper does not support reads
  "Not reported in the retrieved passages"; no cell shows a value that its cited passages do not
  contain (checked as part of SC-002).
- **SC-005**: For every run, the model requests actually made (first attempts) are at most the
  stated cost; with retries included they are at most twice the stated cost, and both figures are
  printed by the checkpoint.
- **SC-006**: A summary costs at most 6 model requests (five sections and one TL;DR), a
  comparison at most one per aspect (at most 5), and a run of
  the full checkpoint stays within its printed plan; the plan fits within one day's free requests
  with at least half of them left.
- **SC-007**: In 100% of scripted tests in which a part has invalid citations, no citations, or a
  cut-off output, only that part is affected, it shows the designed state, and all other parts
  remain visible.
- **SC-008**: No summary section, TL;DR or comparison cell text is visible before its citations
  have been checked; parts appear progressively as they are checked.
- **SC-009**: With fewer requests remaining than a run's stated cost, starting it sends zero model
  requests and shows the daily-limit state.
- **SC-010**: The Summary and Compare screens can be completed at 375 px width without horizontal
  scrolling and with the keyboard alone, and their text meets a 4.5:1 contrast ratio.

## Clarifications

### Session 2026-10-25

- Q: May the researcher type their own comparison aspects, or only pick from a fixed list?
  → A: Fixed list only (Problem, Method, Datasets, Results, Limitations), each with a tested
  query and instruction (FR-007).
- Q: One model request per aspect, or one request for the whole comparison table?
  → A: One request per aspect, a row at a time; cost = number of aspects (FR-009).
- Q: The summary design showed a sixth card (Future work); five sections or six?
  → A: Five sections (FR-002); the sixth card was an example of the not-reported state and is
  relabelled in the design. A summary costs at most 6 requests.
- Q: The compare design said "uses 1 request"; does it override one request per aspect?
  → A: No; one request per aspect stands, and the design now reads "uses 5 requests, 1 per
  aspect".
- Q: Navigation: four header tabs (Ask, Library, Summarize, Compare) as in the summary and
  compare designs? → A: Yes; library.png is updated to match.
- Q: The design shows "4 passages read" per section; use 4 instead of the question default (6)?
  → A: Yes, 4 passages per summary section.

## Assumptions

- **Placement**: the header has four tabs: Ask, Library, Summarize and Compare (`docs/design/`).
  Summarize opens a paper picker with the saved summaries; the Summarize button on a paper's card
  in the Library opens that paper's summary directly. Compare opens the comparison screen.
- **Retrieval sizes**: each summary section uses 4 passages from that paper (as shown in the
  design, fewer than a question's 6, to keep each prompt small); each comparison aspect uses a fixed, equal number of
  passages per paper (default 3), small enough that a row for four papers fits one prompt. Passages
  below the existing relevance threshold count as not retrieved.
- **Facet queries**: each facet and aspect has a fixed, PaperPilot-written retrieval query and
  instruction (for example the Data facet asks for datasets, corpora and benchmarks); the researcher
  does not edit them.
- **Saved results live with the library** on this machine and persist across restarts; they are
  removed with their paper, and stale ones may be kept for reading as "earlier" until replaced.
- **"PaperPilot's instructions have changed"** is detected by a version number of the summary and
  comparison instructions, raised whenever they change.
- **One model task at a time** extends Feature 3's one-question-at-a-time rule; uploads keep running
  in the background as before.
- **The guide** (`docs/paperpilot-guide.pdf`) is referenced but not present locally (constitution);
  this specification follows the description above.

## Dependencies

- Feature 2: the engine's retrieval, prompts, citation validation and the not-found rule.
- Feature 3: the web app, the source viewer with highlights, the designed failure states, the
  shared daily request counter, the long-wait rule and the one-task-at-a-time guard.

## Out of Scope

- Map-reduce summaries of every passage (rejected alternative, FR-006).
- Comparisons of more than 4 papers.
- Exporting summaries or comparisons (PDF, Markdown, copy as table).
- The evaluation harness (scored question sets) — a later feature.
- Editing summaries, or asking follow-up questions about a summary.
