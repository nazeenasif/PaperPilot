# Feature Specification: PaperPilot Web App

**Feature Branch**: `003-web-app`
**Created**: 2026-10-24
**Status**: Draft
**Input**: User description: "Feature 3: PaperPilot web app — FastAPI backend + Next.js frontend for
the library and question answering. Visual reference: docs/design/ask.png, library.png,
states.png (dark cinematic: ink background #07090D, panels #10141B, teal #5EEAD4 for
verified/grounded, amber #F5B454 for citations and highlights; Sora headings, Inter body,
JetBrains Mono for system details). User stories: drag-and-drop PDFs with Parsing → Chunking →
Embedding → Ready progress and duplicate detection; answers with numbered citation chips and an
'all citations verified' badge; citations open the PDF at the cited page with the passage
highlighted; choose which papers a question searches, and follow-ups show what they were searched
as; every failure looks designed and friendly (not-found with suggestions, busy countdown,
daily-limit screen, held-back answer with viewable unverified text, uncited sentences flagged).
Requirements: the Python engine stays the single source of logic and the frontend never calls the
LLM; the embedding model and library load once at start; adding a paper runs in the background
with progress; the API returns everything ask() produces; the UI shows today's request usage
against the daily free limit; phone width, keyboard accessible, 4.5:1 contrast. Out of scope:
summaries, comparison, user accounts, deployment."

## Clarifications

### Session 2026-10-24

- Q: Should answer text stream word by word while the model writes it, before citations are
  verified? → A: No (option A). The answer is shown only after it has been checked; progress
  steps are shown meanwhile. The verified answer then appears with a short entrance animation
  (sentences fade in in sequence, then citation chips, then the verified badge) that completes
  in under 500 ms and is never paced to imitate typing; with reduced motion it appears instantly.
- Q (added by the researcher): What happens when a paper already in the library is added again
  but has no stored PDF? → A: The PDF is saved without re-parsing or re-embedding, and the upload
  reports "PDF attached" instead of "already present".
  *Amended 2026-10-24 (after planning)*: attaching also builds the highlight layout in the same
  background job, as its own "Mapping highlights" step (parse and chunk only, never embedding),
  accepted only if every regenerated passage id and text matches what is stored. If the check
  fails, no layout is stored; citations then open the cited page without a highlight and offer
  "Re-process paper for exact highlights".
- Q: Who can reach the app over the network? → A: Localhost only — the server accepts
  connections only from the same machine; phone width is a narrow-window layout requirement,
  not access from other devices.
- Q: Which requests does the "Requests today" counter include? → A: Every request the engine
  makes — web app, checkpoint scripts and any other caller — in one shared, persistent daily
  counter.
- Q: What happens when the provider asks for a wait longer than the retry cap? → A: No retry:
  the question ends at once and shows the daily-limit state, or "try again at <time>" when it is
  not the daily limit.
- Refinements from the researcher after the questions: both the API and the frontend dev server
  bind explicitly to 127.0.0.1 (the frontend dev server otherwise listens on all interfaces) and
  the API accepts cross-origin requests only from the frontend's localhost origin; network
  access, authentication and deployment are a later feature. A long requested wait raises a
  readable "rate limited until <time>" error from the engine. X-RateLimit-Reset is trusted only
  when it resolves to a future time within 48 hours, otherwise normal backoff applies; its units
  are confirmed from the first real 429. The daily-counter rules (FR-025) are restated unchanged.

## User Scenarios & Testing *(mandatory)*

The researcher runs PaperPilot on their own machine and uses it in a browser. Feature 1 (the
paper library and search) and Feature 2 (grounded answers with checked citations) already work
from scripts; this feature makes them usable through a web interface that follows the visual
reference in `docs/design/` (Ask, Library and Designed States screens).

### User Story 1 - Ask a question and get a verified, cited answer (Priority: P1)

The researcher types a question about their papers and receives an answer whose sentences carry
numbered citation chips. When every citation was checked against the passages the model was
given, the answer shows an "All citations verified" badge. While the answer is being prepared,
the researcher sees what is happening (for example "Reading 6 passages from 2 papers…").

**Why this priority**: answering questions from the papers, with sources visible, is the reason
PaperPilot exists. Every other story builds on this screen.

**Independent Test**: with the 5 test papers already in the library, ask "What is LoRA?" and
confirm the answer appears with numbered chips, the verified badge, the number of passages read
and the time taken.

**Acceptance Scenarios**:

1. **Given** a library with papers, **When** the researcher asks an answerable question, **Then**
   the answer appears with one numbered chip per citation, each chip number matching a passage
   the answer was built from, and an "All citations verified" badge.
2. **Given** a question is being answered, **When** the researcher waits, **Then** a working state
   names the step in progress (searching, reading N passages from M papers, checking citations)
   and the page never appears frozen.
3. **Given** an answer, **When** the researcher looks at its details, **Then** they can see how
   many passages were read, how long the answer took, and the model used.
4. **Given** the researcher presses Enter (or the send button) with an empty question, **Then**
   nothing is sent and the input explains that a question is needed.
5. **Given** an answer has been checked, **When** it is shown, **Then** its sentences fade in in
   sequence, followed by the citation chips and then the verified badge, all within 500 ms; no
   part of the answer is shown before it was checked, and with reduced motion it appears at once.

---

### User Story 2 - Open a citation in the source PDF (Priority: P1)

The researcher clicks (or keyboard-activates) a citation chip. A source viewer opens beside the
answer (full screen on a phone) showing the cited paper's title, section, page ("page 5 of 26")
and similarity score, with the actual PDF page displayed and the retrieved passage highlighted.
The researcher can open the full PDF.

**Why this priority**: the constitution requires grounding to be visible (Principle IX); a
citation that cannot be checked in one click is not trustworthy.

**Independent Test**: after an answer with citations, activate chip [1] and confirm the viewer
shows the right paper at the cited page with the passage text highlighted on that page.

**Acceptance Scenarios**:

1. **Given** an answer with citation [n], **When** the researcher activates chip [n], **Then** the
   viewer shows passage n's paper title, section, page number, total pages and score, and
   renders that page of the PDF.
2. **Given** the viewer is open, **When** the page is shown, **Then** the passage's text on that
   page is highlighted, and a note says the highlighted text is exactly what the model read.
3. **Given** the passage's text cannot be located on the rendered page (for example it continues
   onto the next page or the PDF's text layer differs), **When** the viewer opens, **Then** the
   page is still shown and the passage text is displayed alongside it, with a note that the exact
   location could not be marked.
4. **Given** the viewer is open, **When** the researcher chooses "Open full PDF", **Then** the
   whole paper opens at the cited page.
5. **Given** a paper whose original PDF is not available to PaperPilot, **When** its citation is
   activated, **Then** the viewer shows the passage text with its title, section and page and
   explains that the PDF can be shown after the paper's file is added again (which attaches the
   PDF without re-embedding; see User Story 3, scenario 4).
6. **Given** a paper whose PDF was attached but whose highlight layout could not be verified,
   **When** its citation is activated, **Then** the viewer opens the cited page without a
   highlight, shows the passage text alongside, and offers "Re-process paper for exact
   highlights".
7. **Given** that offer, **When** the researcher confirms it, **Then** the paper is processed again
   from its stored PDF as a background job with the usual phases, and afterwards its citations
   open with exact highlights.

---

### User Story 3 - Add papers and watch them become searchable (Priority: P2)

On the Library screen the researcher drags PDFs onto a drop area (or chooses files). Each file
shows its progress through Parsing → Chunking → Embedding → Ready, with a percentage during
embedding. When ready, the paper appears as a card with its title, number of passages (split into
text and table passages), sections and pages. A file already in the library is recognised and
not processed again. The Library header summarises the library ("5 papers, 223 searchable
passages") and states that embeddings run on this machine.

**Why this priority**: the library can already be filled from a script, so asking (P1) delivers
value first; adding papers in the browser is what makes the app self-contained.

**Independent Test**: drop a new PDF and watch it reach Ready with its card and counts; drop the
same PDF again and confirm it is reported as already in the library without reprocessing.

**Acceptance Scenarios**:

1. **Given** the Library screen, **When** the researcher drops one or more PDFs, **Then** each file
   gets its own progress row showing the current phase, and the researcher can keep using the app
   (including asking questions) while files are processed.
2. **Given** a file finishes, **Then** its card shows title, passage count (text and table),
   section count and page count, and the library summary updates.
3. **Given** a file whose content is already in the library (even under another file name) and
   whose PDF is stored, **When** it is dropped, **Then** it is marked "Already in your library"
   with a link to the existing card, and no processing happens.
4. **Given** a file whose content is already in the library but whose PDF is not stored (for
   example a paper added from a script before this feature), **When** it is dropped, **Then** the
   PDF is saved, the row shows a "Mapping highlights" step while the passage layout is built
   (no embedding), and the row reports "PDF attached"; the paper's citations can now open the PDF
   with highlights — or, if the layout could not be verified against the stored passages, the
   row says so and citations open without highlights (User Story 2, scenarios 6–7).
5. **Given** a file that is not a PDF, is larger than the size limit, has no extractable text
   (for example a scanned image), or cannot be read, **When** it is dropped, **Then** its row
   ends in a friendly explanation of the problem and what to try, and nothing is added.
6. **Given** a paper card, **When** the researcher chooses delete and confirms, **Then** the paper
   and its passages leave the library and the summary updates; cancelling changes nothing.
7. **Given** a paper card, **When** the researcher chooses "Ask this paper", **Then** the Ask
   screen opens with only that paper selected.

---

### User Story 4 - Choose which papers a question searches; follow-ups show their search (Priority: P2)

On the Ask screen a library panel lists every paper with a checkbox and its passage count, and a
scope line reads "Search scope · 3 of 5 papers". Questions search only the selected papers.
Follow-up questions in the same conversation are understood in context, and each follow-up shows
what it was actually searched as (for example: Searched as "What are the limitations of LoRA?").

**Why this priority**: scoping and follow-ups are already supported by the engine; exposing them
makes conversations natural and lets the researcher focus on one paper.

**Independent Test**: select only the BERT paper and ask about its training data; confirm every
cited passage is from BERT. Then ask "What is LoRA?" with all papers selected, follow with "What
are its limitations?", and confirm the follow-up shows its rewritten search.

**Acceptance Scenarios**:

1. **Given** 2 of 5 papers selected, **When** a question is asked, **Then** every passage and
   citation in the answer comes from those 2 papers.
2. **Given** the researcher tries to deselect the last selected paper, **Then** the app keeps at
   least one paper selected (or disables sending) and says why.
3. **Given** an earlier question and answer, **When** the researcher asks a follow-up that refers
   back to it, **Then** the answer shows "Searched as" with the standalone question used.
4. **Given** the follow-up could not be rewritten, **Then** the answer notes that the question was
   searched as typed.
5. **Given** a conversation, **When** the researcher starts a new conversation, **Then** earlier
   turns no longer influence follow-ups.

---

### User Story 5 - Every failure is designed and friendly (Priority: P2)

Whatever goes wrong, the researcher sees a designed state that says what happened and what they
can do — never a raw error, stack trace or provider message (states.png):

- **Not found**: "I couldn't find that in the selected papers." with suggestions such as
  "Search all papers" (when not all are selected) and "Rephrase more specifically".
- **Busy, retrying**: when the free model is rate-limited or slow, a countdown to the next
  attempt with "attempt N of M", stating that the question is safe and will be retried.
- **Daily limit**: when today's free requests are used up, the usage (for example 50 / 50), when
  answers resume in the researcher's local time, and that search and the PDF viewer keep working,
  with "Browse passages instead".
- **Answer held back**: when the model cited a passage it was not given (or cited nothing), the
  not-found sentence with an explanation ("The model cited passage 7, but only 6 were
  provided…") and "View the unverified answer", which reveals the original text clearly marked
  as unverified.
- **Uncited sentence**: an otherwise verified answer with a sentence that carries no citation
  shows that sentence with a dotted underline and a "1 sentence has no citation" note; the answer
  is not blocked.

**Why this priority**: required by the constitution (Principle IX) and by the free tier's
reality; without it the app looks broken on the most common free-tier events.

**Independent Test**: trigger each state (off-topic question; simulated rate limit; daily limit
reached; a reply citing a missing passage; a reply with an uncited sentence) and confirm each
designed presentation, with no raw error text anywhere.

**Acceptance Scenarios**:

1. **Given** an off-topic question, **Then** the not-found state appears with suggestions; choosing
   "Search all papers" re-asks with every paper selected.
2. **Given** the model is rate-limited and the engine waits before retrying, **Then** a countdown
   shows the wait and the attempt number, and the answer appears normally if a retry succeeds.
3. **Given** the provider asks for a wait longer than the retry cap (for example until its
   daily reset), **Then** no retry is made and the daily-limit state (or "try again at <time>")
   appears at once.
4. **Given** all retries fail, **Then** a friendly message says the free model is busy and offers
   to try again, keeping the question text.
5. **Given** today's usage has reached the daily limit, **When** the researcher asks a question,
   **Then** no model request is made and the daily-limit state appears; "Browse passages instead"
   shows the matching passages for the question with their papers, sections and pages.
6. **Given** an answer held back for invalid or missing citations, **When** the researcher chooses
   "View the unverified answer", **Then** the original text appears, clearly labelled as not
   verified, with its invalid citation numbers indicated.
7. **Given** an answer with uncited sentences, **Then** those sentences are visually flagged and the
   badge does not claim that every sentence is cited.
8. **Given** the server is not running or stops responding, **Then** the app shows that PaperPilot
   cannot be reached and how to start it, and recovers by itself when the server returns.
9. **Given** the server is still loading the embedding model at startup, **Then** the app shows a
   "Getting ready" state instead of failing requests.

### Edge Cases

- Empty library: the Ask screen invites the researcher to add papers first; asking is disabled.
- The researcher asks while a paper is still being added: the question searches the papers that
  are ready; the new paper is not selectable until Ready.
- Two files dropped at once with the same content: one is processed, the other is reported as a
  duplicate.
- A paper is deleted while its citation is open in the viewer: the viewer says the paper was
  removed.
- A question is sent while another is being answered: sending is disabled until the current answer
  finishes (one question at a time).
- Very long answers or titles: text wraps; nothing overflows horizontally at phone width.
- The provider changes or withdraws the free model: the model failure is shown as a designed
  state naming the configured model and pointing to the settings.
- The daily usage counter crosses midnight in the provider's reset time zone while the app is
  open: usage resets and the daily-limit state clears.
- A paper added before this feature (no stored PDF copy): see User Story 2, scenario 5.

## Requirements *(mandatory)*

### Functional Requirements

**Architecture boundaries**

- **FR-001**: All library, search, answering, citation-checking and rewriting logic MUST come from
  the existing PaperPilot engine; the web layer MUST only pass requests to it and present its
  results (constitution Principles II and IX).
- **FR-002**: The browser MUST NOT contact the language model or hold any API key; no secret may
  appear in anything delivered to the browser.
- **FR-002a**: Both the API server and the frontend dev server MUST bind explicitly to 127.0.0.1,
  never to all interfaces (the frontend dev server's default), so neither is reachable from other
  devices on the network; the API MUST accept cross-origin requests only from the frontend's
  localhost origin. No sign-in is required.
- **FR-003**: The embedding model and the library MUST be loaded once when the server starts; the
  app MUST report a "getting ready" status until loading is complete.

**Asking (User Stories 1, 4, 5)**

- **FR-004**: The researcher MUST be able to ask a question about the selected papers; the answer
  MUST include everything the engine returns: answer text, citation report (valid numbers,
  invalid numbers, uncited sentences), numbered passages with paper title, section, page and
  score, not-found flag, fallback reason, warning, the unverified original text when an answer
  was held back, the original and standalone question, whether a rewrite was applied and why it
  fell back, timings (rewrite, retrieve, generate), token counts when available, and the number
  of model requests used.
- **FR-005**: Citation numbers in the answer MUST be shown as interactive chips; the "All
  citations verified" badge MUST appear only when the citation report has no invalid numbers and
  the answer is not the not-found sentence.
- **FR-006**: While a question is processed, the app MUST show the current step (rewriting,
  searching, reading N passages from M papers, waiting to retry, checking citations).
- **FR-007**: The not-found answer MUST be shown exactly as the engine's sentence, never reworded.
- **FR-008**: The researcher MUST be able to select which ready papers a question searches; at
  least one paper MUST be selected to send a question.
- **FR-009**: The app MUST keep the current conversation's turns and send them with follow-up
  questions; each follow-up MUST display the standalone question it was searched as. The
  researcher MUST be able to start a new conversation.
- **FR-010**: Only one question MAY be in progress at a time.
- **FR-011**: Answer text MUST NOT be shown before the engine has checked its citations; until
  then only the progress steps of FR-006 are shown. The checked answer MUST then appear with an
  entrance animation — sentences fade in in sequence, then the citation chips, then the verified
  badge — completing in under 500 ms and never paced to imitate typing. With a reduced-motion
  preference it MUST appear instantly. (The mock-up's "Streaming" card is replaced by this.)

**Source viewer (User Story 2)**

- **FR-012**: Activating a citation chip MUST open a source viewer for that passage showing paper
  title, section, page number and total pages, score, and the PDF page itself.
- **FR-013**: The viewer MUST highlight the passage's text on the displayed page; when the exact
  location cannot be found, it MUST show the passage text alongside the page with a note. When
  the reason is a paper whose attached PDF could not be matched to its stored passages, the
  viewer MUST also offer "Re-process paper for exact highlights" (FR-018a).
- **FR-014**: The viewer MUST offer opening the full PDF at the cited page.
- **FR-015**: PaperPilot MUST keep a local copy of each added PDF so citations can open it; the
  copies MUST stay on the researcher's machine and out of version control (constitution
  Principle VI), and MUST be removed when the paper is deleted.

**Library (User Story 3)**

- **FR-016**: The researcher MUST be able to add PDFs by drag and drop and by a file chooser,
  several at a time.
- **FR-017**: Adding a paper MUST run in the background and report its phase (Parsing, Chunking,
  Embedding with percentage, Ready, or Failed with a reason); the rest of the app MUST stay usable.
- **FR-018**: Files MUST be rejected with a friendly reason when they are not PDFs, exceed 25 MB,
  have no extractable text, or cannot be read. A file whose content is already in the library
  MUST NOT be embedded again: if the paper's PDF is already stored it MUST be reported as
  "already present" with no processing; if not, the PDF MUST be stored and, in the same
  background job, its highlight layout built as a separate "Mapping highlights" step (parse and
  chunk only, no embedding). The layout MUST be stored only if every regenerated passage id and
  text equals the stored passage; otherwise no layout is stored and the job reports that
  highlights are unavailable. Either way the upload is reported as "PDF attached".
- **FR-018a**: For a paper with a stored PDF but no verified layout, the researcher MUST be able
  to re-process the paper from its stored PDF (parse, chunk, embed, layout) as a background job
  with the usual phases; the paper's passages are replaced only after the new ones are fully
  prepared, so a failure leaves the paper as it was.
- **FR-019**: Each paper card MUST show title, passage count split into text and table passages,
  section count and page count, plus its arXiv identifier when one is found in the paper; the
  Library header MUST show the total number of papers and passages.
- **FR-020**: The researcher MUST be able to delete a paper after a confirmation step.
- **FR-021**: "Ask this paper" on a card MUST open the Ask screen with only that paper selected.

**Failure states and request usage (User Story 5)**

- **FR-022**: Each failure MUST have a designed presentation: not found (with suggestions), busy
  and retrying (countdown, attempt N of M), all retries failed (try again, question kept), daily
  limit reached, answer held back (with viewable unverified text), uncited sentences flagged,
  invalid or failed upload, model unavailable or misconfigured, server unreachable, server
  getting ready. No raw error text, stack trace or provider message MAY be shown.
- **FR-023**: When the engine waits before retrying a model request, the app MUST show the wait as
  a live countdown with the attempt number and the maximum number of attempts.
- **FR-023a**: When the provider asks for a wait longer than the engine's retry wait cap
  (60 seconds), the engine MUST stop retrying at once, make no further model requests, and raise
  a readable "rate limited until <time>" error. The app MUST show the daily-limit state when the
  daily quota is exhausted, otherwise a "try again at <local time>" state with the question kept.
- **FR-023b**: The engine MUST trust a rate-limit reset time from the provider (X-RateLimit-Reset)
  only when it resolves to a time in the future and within 48 hours; any other value MUST be
  ignored and the normal backoff applied. The header's units MUST be confirmed from the first
  real 429 response and recorded (research), and the engine adjusted if they differ.
- **FR-023c**: FR-023a and FR-023b MUST be implemented in the engine's single LLM module and
  covered by offline tests with the fake model client (long wait, wait at the cap, reset in the
  past, reset beyond 48 hours, reset in the wrong units).
- **FR-024**: The app MUST always show today's model request usage against the daily free limit
  (for example "Requests today 33 / 50") and the configured model, labelled as free when it is a
  free model.
- **FR-025**: Request usage MUST count every model request the PaperPilot engine makes, whoever
  the caller is (the web app, checkpoint and calibration scripts, or any other use of the
  engine), including first attempts and retries, in one shared daily counter that persists
  across restarts and resets at the provider's daily reset time (to be verified during planning;
  expected 00:00 UTC); the daily limit MUST be a setting (default 50). Whenever a provider
  response reports its own remaining-requests figure, that figure MUST replace PaperPilot's
  estimate. Callers running at the same time (the app and a script) MUST NOT lose counts.
- **FR-026**: When usage has reached the daily limit, asking MUST NOT contact the model; the app
  MUST show the daily-limit state with the local time when answers resume, and MUST keep search
  and the source viewer working, including "Browse passages instead", which lists the passages
  matching the question.
- **FR-027**: When the provider itself reports that the daily limit is reached, the app MUST show
  the daily-limit state even if PaperPilot's own count is lower.

**Presentation and accessibility**

- **FR-028**: The app MUST follow the visual reference in `docs/design/`: dark ink background and
  panels, teal for verified and grounded elements, amber for citations and highlights, and
  separate typefaces for headings, body text and system details (palette and fonts as in the
  feature description).
- **FR-029**: Every user story MUST be completable in a phone-width window (375 px) without
  horizontal scrolling (a layout requirement; the app is used on the same machine, FR-002a); on narrow screens the library panel and the source viewer open as overlays.
- **FR-030**: Every user story MUST be completable with the keyboard alone, with a visible focus
  indicator, and citation chips, checkboxes and the viewer MUST be reachable and operable by
  keyboard and announced meaningfully by screen readers.
- **FR-031**: All text MUST have a contrast ratio of at least 4.5:1 against its background,
  including text on teal and amber elements and the highlighted passage.
- **FR-032**: Animations MUST respect the researcher's reduced-motion preference.

**Checkpoint**

- **FR-033**: The feature MUST include a runnable checkpoint that exercises each user story and
  demonstrates every failure state in FR-022 (constitution quality gates), within a stated model
  request plan and using simulated model responses for the failure states.

### Key Entities

- **Paper card**: a paper in the library — title, passage counts (text and table), section count,
  page count, optional arXiv identifier, whether its PDF copy is available, and whether exact
  highlights are available.
- **Upload job**: one file being added, or one paper being re-processed — file name, phase
  (including "Mapping highlights" for an attach), embedding percentage, outcome (ready, already
  present, PDF attached to an existing paper with or without highlights, re-processed, or failed
  with a reason).
- **Conversation**: the ordered question and answer turns on the Ask screen, plus the selected
  papers; it lasts until the researcher starts a new one or reloads the page.
- **Answer view**: everything from FR-004, plus its presentation state (verified, uncited flags,
  held back, not found).
- **Source view**: one cited passage — paper, section, page, total pages, score, passage text,
  highlight found or not.
- **Request usage**: today's request count, the daily limit, the reset time, and the configured
  model.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For the checkpoint questions, 100% of citation chips open the cited paper at the
  cited page.
- **SC-002**: For the checkpoint questions, at least 90% of opened citations show the passage
  highlighted on the page; the rest show the passage text alongside with the "location not
  marked" note.
- **SC-003**: Every failure state listed in FR-022 is demonstrated in the checkpoint, and in none
  of them does a raw error, stack trace, provider message or API key appear on screen.
- **SC-004**: A 20-page text PDF reaches Ready within 60 seconds on the development machine, with
  at least three phase changes visible along the way; re-adding it is reported as already present
  within 3 seconds, and re-adding a paper that has no stored PDF reports "PDF attached" within 10
  seconds (including the "Mapping highlights" step) with no embedding.
- **SC-005**: After the app reports ready, the first question's search step takes under 2
  seconds (no model loading happens per request).
- **SC-006**: The request usage shown in the app equals the number of model requests the engine
  made today from any caller (app and scripts), including retries, and is unchanged by a server
  restart.
- **SC-007**: With usage at the daily limit, asking makes zero model requests and "Browse
  passages instead" returns matching passages.
- **SC-008**: All five user stories can be completed at 375 px width without horizontal
  scrolling, and with the keyboard alone.
- **SC-009**: 100% of text measured on the Ask, Library and failure-state screens meets a 4.5:1
  contrast ratio.
- **SC-010**: Zero occurrences of the API key in anything delivered to the browser, in the
  browser's stored data, or in server logs.
- **SC-011**: No answer text is visible before its citations are checked, and a checked answer
  finishes appearing (text, chips and badge) within 0.5 seconds; with reduced motion it appears in
  a single step.
- **SC-012**: Neither the API nor the frontend accepts a connection on the machine's network
  address (only on 127.0.0.1), and the API refuses cross-origin requests from any origin other
  than the frontend's.
- **SC-013**: When the provider asks for a wait longer than 60 seconds, the question ends with
  exactly one model request spent and the matching designed state shown.

## Assumptions

- PaperPilot runs on the researcher's own machine for a single user; the server and the app are
  opened locally and both servers listen on 127.0.0.1 only (FR-002a), so no accounts are needed.
- Two provider facts are unverified and must be checked during planning or the first real
  run: the daily reset time (expected 00:00 UTC) and the units of X-RateLimit-Reset (currently
  read as epoch milliseconds; the 48-hour rule of FR-023b makes a wrong unit fall back safely to
  normal backoff).
- The five test papers' files are dropped into the app once to attach their PDFs and build their
  highlight layouts (no re-embedding); until then User Story 2 scenario 5 applies. Their stored
  passages were made with the current chunk settings, so the layout check is expected to pass.
- The provider's daily free limit resets at midnight UTC (OpenRouter); the app shows the reset in
  the researcher's local time. Requests made with the same key outside the PaperPilot engine
  (other tools, the provider's website) cannot be seen and are not counted; the provider's own
  remaining-requests figure and daily-limit response cover that case (FR-025, FR-027).
- The maximum number of attempts in the busy state comes from the engine's retry policy (currently
  4), not from the design mock-up's "attempt 1 of 3".
- Conversations are kept in the browser only for the current page session, as in Feature 2,
  where the caller supplies the history.
- The 25 MB upload limit comes from the Library mock-up.

## Dependencies

- Features 1 and 2 (library, search, `ask()` with citation checks and follow-up rewriting).
- Engine additions this feature needs, kept inside the engine (FR-001): storing a copy of each
  added PDF; attaching a PDF to a paper already in the library with a verified layout and no
  re-embedding; re-processing a paper from its stored PDF;
  reporting ingest phases and embedding progress; reporting retry waits and attempt numbers
  during a question; not retrying when the provider's requested wait exceeds the cap, and
  trusting X-RateLimit-Reset only within 48 hours (FR-023a–FR-023c, an amendment to ADR-0003's
  retry policy); a persistent, shared daily request count that
  accepts the provider's remaining-requests figure; per-paper section and text/table passage
  counts; and the arXiv identifier when present.
- Constitution v1.3.0 Principle IX and the web stack it names.

## Out of Scope

- Paper summaries ("Summarize" on the cards) and paper comparison (the "Compare" tab); they appear
  in the mock-ups but are not built and are not shown.
- Network access from other devices, authentication, user accounts, sharing and deployment;
  these are a later feature (this one is localhost only, FR-002a).
- Storing conversations across page reloads.
- Changing answering, retrieval or citation rules; this feature presents the engine's behaviour.
