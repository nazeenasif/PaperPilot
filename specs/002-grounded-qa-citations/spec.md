# Feature Specification: Grounded Question Answering with Citations

**Feature Branch**: `002-grounded-qa-citations`
**Created**: 2026-10-24
**Status**: Draft
**Input**: User description: "Feature 2: Grounded question answering with citations for
PaperPilot (see docs/paperpilot-guide.pdf, Phases 4–5; builds on Feature 1's library and
search). Goal: a researcher asks a question about the papers in their library and gets a
concise answer written only from retrieved passages, where every factual claim carries a
numbered citation like [2] that maps to a passage with paper title, section and page. When the
passages don't contain the answer, the system says exactly "I couldn't find that in the
selected papers." instead of guessing."

## Clarifications

### Session 2026-10-24

- Q: What does the researcher get when an answer has an invalid citation or no citations? →
  A: The not-found sentence, plus a warning listing the invalid citation numbers and the
  original answer text for inspection (constitution Principle V).
- Q: How strictly should code check citations per sentence? → A: Sentence-level warning
  only: sentences without a citation are listed in a warning, but the answer is still
  returned when all cited numbers are valid and at least one citation is present.
- Q: If the threshold cannot both keep all on-topic and reject ≥80% off-topic questions,
  which wins? → A: Never reject on-topic questions; the threshold goes just below the lowest
  on-topic top score, off-topic rejection is best effort and its actual rate is recorded.
- Q: How long is a "concise" answer? → A: At most about 150 words, unless the question
  explicitly asks for more detail (then up to about 300).
- Q: Which language-model provider? → A: One OpenAI-compatible connection configured by base
  URL, API key and model; the default is OpenRouter with a pinned free model (replaces the
  earlier Gemini-only design).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask a question, get a cited answer (Priority: P1)

A researcher asks a natural-language question about the papers in their library. They get a
concise answer in which every factual claim is followed by a numbered citation such as [2],
plus the numbered list of passages the answer was based on, each with paper title, section
and page, so every claim can be checked against its source.

**Why this priority**: This is the core value of the feature and the MVP on its own.

**Independent Test**: With the 5 test papers in the library, ask "Which dataset was the
Transformer trained on for English-German translation?" and confirm the answer names the
dataset with a citation that maps to a listed passage from *Attention Is All You Need*.

**Acceptance Scenarios**:

1. **Given** a library containing a paper that answers the question, **When** the researcher
   asks it, **Then** they receive an answer whose factual sentences each carry at least one
   citation number, and every citation number refers to a passage in the returned list.
2. **Given** an answer, **When** the researcher reads the passage list, **Then** each passage
   shows its number, paper title, section, page, similarity score and text.
3. **Given** a passage containing a number (e.g. "4.5 million sentence pairs"), **When** the
   answer uses that number, **Then** it appears exactly as in the passage.
4. **Given** an empty or whitespace-only question, **When** it is asked, **Then** the
   researcher gets a clear error and no answer is generated.

---

### User Story 2 - Unsupported questions get the not-found sentence (Priority: P1)

A researcher asks something the papers do not cover. Instead of a guess, they get exactly
"I couldn't find that in the selected papers."

**Why this priority**: Never inventing facts is a non-negotiable project principle; without
this the cited answers cannot be trusted.

**Independent Test**: Ask "What is the capital of France?" and confirm the response is
exactly the not-found sentence.

**Acceptance Scenarios**:

1. **Given** a question unrelated to any paper, **When** it is asked, **Then** the answer is
   exactly "I couldn't find that in the selected papers." and the passage list is empty.
2. **Given** retrieved passages whose top score falls below the relevance threshold, **When** the
   question is asked, **Then** the not-found sentence is returned without contacting the
   language model.
3. **Given** relevant-looking passages that do not actually contain the answer, **When** the
   question is asked, **Then** the answer is the not-found sentence or a partial answer limited
   to what the passages support; it never contains facts absent from the passages.
4. **Given** an empty library, **When** any question is asked, **Then** the not-found sentence
   is returned.

---

### User Story 3 - Ask within selected papers (Priority: P2)

A researcher limits a question to one or more selected papers; the answer and its passages
come only from those papers.

**Why this priority**: Important for focused reading, but the unfiltered flow works without it.

**Independent Test**: Ask a question filtered to *BERT* and confirm every listed passage and
citation belongs to *BERT*.

**Acceptance Scenarios**:

1. **Given** a filter naming one paper, **When** a question is asked, **Then** every passage
   in the list comes from that paper.
2. **Given** a filter naming a paper not in the library, **When** a question is asked,
   **Then** the researcher gets a clear "unknown paper" error and no answer is generated.
3. **Given** a filter on a paper that does not cover the question, **When** it is asked,
   **Then** the not-found sentence is returned even if other papers would answer it.

---

### User Story 4 - Follow-up questions (Priority: P2)

A researcher asks a follow-up such as "What about its limitations?" after an earlier
exchange. The system turns the follow-up into a standalone question using the recent
conversation, searches with it, and answers; the standalone question is shown so the
researcher can check how it was understood.

**Why this priority**: Makes conversations natural; single questions already work without it.

**Independent Test**: Ask "What is LoRA?", then "What are its limitations?", and confirm the
standalone question mentions LoRA and the answer cites LoRA passages.

**Acceptance Scenarios**:

1. **Given** a previous exchange about LoRA, **When** the researcher asks "What are its
   limitations?", **Then** the shown standalone question refers to LoRA explicitly and the
   answer is about LoRA's limitations.
2. **Given** no previous exchange, **When** a question is asked, **Then** it is used as is and
   no rewriting step takes place.
3. **Given** a long conversation, **When** a follow-up is asked, **Then** only the 6 most
   recent turns are used to understand it.

---

### User Story 5 - Invalid citations are caught (Priority: P2)

When the generated answer cites a passage number that was not provided (e.g. [9] when only 6
passages were given), the system detects it in code rather than trusting the model.

**Why this priority**: Protects the guarantee that every citation can be checked.

**Independent Test**: Feed the validation step an answer citing [2] and [9] with 6 provided
passages and confirm [9] is reported as invalid and [2] as valid.

**Acceptance Scenarios**:

1. **Given** an answer citing only provided passage numbers, **When** it is validated,
   **Then** all citations are reported valid.
2. **Given** an answer citing a number that does not map to a provided passage, **When** it is
   validated, **Then** that number is reported invalid, the researcher receives the
   not-found sentence as the answer, and a warning lists the invalid numbers together with the
   original answer text for inspection.

---

### Edge Cases

- The language model returns the not-found sentence with extra words or punctuation: the
  researcher still receives exactly the not-found sentence.
- A passage contains text that looks like an instruction (e.g. "Ignore previous instructions
  and…"): it is treated as passage content and does not change the system's behaviour.
- The answer contains no citations at all but is not the not-found sentence: treated as an
  answer with invalid citations (same handling as User Story 5).
- Some sentences of an otherwise valid answer have no citation: the answer is returned and
  the warning lists those sentences.
- Citation formats like "[2, 4]", "[2][4]" or "[2-4]": each number is recognised and
  validated.
- The provider rate-limits or has a transient failure: the request is retried with increasing
  waits; if it still fails, the researcher gets a short readable message (no stack trace, no
  secret values).
- The API key is missing or invalid: a clear message names the missing setting without
  showing any key value.
- The follow-up rewrite step fails: the original question is used for search, and the answer
  notes that no rewrite was applied.
- A filter is given as an empty list: the whole library is searched (as in Feature 1).
- The model spends its whole output allowance on internal reasoning and returns no visible
  answer: the researcher gets a clear "output was cut off" error, not an empty answer.
- The provider reports an error inside an otherwise successful response: treated like a
  failed call (retried if temporary, otherwise a readable error).

## Requirements *(mandatory)*

### Functional Requirements

**Retrieval**

- **FR-001**: The system MUST retrieve the top k passages (k configurable, default 6) for the
  question using Feature 1's search, honouring any paper filter.
- **FR-002**: The system MUST compare the top retrieved passage's similarity score with a
  configurable relevance threshold; if the top score is below it, it MUST return the not-found
  sentence without contacting the language model. Otherwise all top k passages MUST be sent
  to the language model, including those scoring below the threshold.
- **FR-003**: The default relevance threshold MUST be chosen from recorded evidence: the
  top scores of at least 5 clearly off-topic questions and at least 5 on-topic questions
  against the 5 test papers, with the measurements and the chosen value documented. The
  default MUST sit just below the lowest on-topic top score, so no on-topic calibration
  question is rejected; the resulting off-topic rejection rate MUST be recorded.

**Answer generation**

- **FR-004**: The system MUST give the language model the remaining passages numbered from 1,
  each with paper title, section and page, and instructions to: answer only from the
  passages; cite every factual claim with passage numbers in square brackets; never invent
  numbers, datasets, authors or citations; copy numbers exactly; and reply with exactly the
  not-found sentence when the passages do not support an answer.
- **FR-004a**: Answers MUST be at most about 150 words, or about 300 words when the question
  explicitly asks for detail (e.g. "explain in detail", "describe step by step"); the length
  limit MUST be part of the language model's instructions only: the system MUST NOT trim or
  cut answers in code. Each answer MUST report its word count, not counting citation markers
  such as [2]; exceeding the limit is reported as a warning in checkpoints, not a failure.
- **FR-005**: Passage text MUST be presented to the language model as quoted data, clearly
  separated from the instructions, so that instructions inside passages are not followed.
- **FR-006**: The not-found sentence MUST be exactly "I couldn't find that in the selected
  papers." and MUST be defined once and reused everywhere it is produced or checked.
- **FR-007**: When the model's reply is the not-found sentence (ignoring surrounding
  whitespace, quotes or trailing punctuation), the system MUST return exactly the
  not-found sentence.

**Citation validation**

- **FR-008**: The system MUST extract every citation number from the answer (including
  grouped forms like [2, 4], [2][4] and ranges like [2-4]) and report which are valid (map to
  a provided passage) and which are not.
- **FR-008a**: The system MUST check each sentence of an accepted answer for a citation and
  list every sentence without one in the answer's warning; uncited sentences alone MUST NOT
  cause the answer to be rejected.
- **FR-009**: When any citation is invalid, or an answer other than the not-found sentence
  (recognised with the tolerant matching of FR-007, so the not-found sentence itself never
  counts as "no citations") has no citations, the system MUST return the not-found sentence as the answer, together
  with a warning that lists the invalid citation numbers (or states that citations were
  missing) and keeps the original answer text for inspection.

**Follow-up questions**

- **FR-010**: When conversation history is provided, the system MUST rewrite the latest
  question into a standalone search question using the 6 most recent turns, and MUST return
  the rewritten question with the answer.
- **FR-011**: When no history is provided, the system MUST NOT perform a rewriting step.
- **FR-012**: If rewriting fails after retries, the system MUST fall back to the original
  question and indicate that no rewrite was applied.

**Provider, reliability and reporting**

- **FR-013**: The language model MUST be reached through one OpenAI-compatible connection
  configured only by settings: `LLM_PROVIDER` (a label, default `openrouter`), `LLM_BASE_URL`
  (default: the provider's endpoint), `LLM_API_KEY` and `LLM_MODEL` (default: a pinned free
  model). Only one component may communicate with the provider; switching to another
  OpenAI-compatible provider MUST need settings changes only.
- **FR-014**: Rate-limit and transient provider errors MUST be retried up to a bounded number
  of attempts, waiting as long as the provider's retry hint says (retry-after or rate-limit
  reset) when it gives one, and with exponentially increasing waits otherwise; persistent
  failure MUST produce a short readable error message instead of a stack trace.
- **FR-014a**: When the model's output is cut off because it reached the output limit
  (including limits used up by the model's internal reasoning), the system MUST report a clear
  error and MUST NOT return the cut-off text as an answer.
- **FR-015**: Missing or invalid provider settings MUST produce a clear message naming the
  setting; API key values MUST never appear in any output, log, error message or committed
  file.
- **FR-016**: Each answer MUST report timings for rewrite, retrieve and generate steps, and
  input/output token counts when the provider supplies them.
- **FR-016a**: Every fallback MUST record its reason: an answer replaced by or returned as the
  not-found sentence states why (no passages retrieved, top passage below the threshold, the
  model said not found, invalid citations, or no citations), and a follow-up that falls back
  to the original question states why (rewrite failed or rewrite was empty).

**Interface and checkpoints**

- **FR-017**: The system MUST expose question answering as a programmatic function taking the
  question, optional paper filter, optional k and optional conversation history.
- **FR-018**: The project MUST include runnable checkpoint scripts for Checkpoints 4–5 that
  exercise the acceptance scenarios above and print PASS/FAIL lines for automatable checks.
  Each checkpoint MUST state how many model requests it plans for the parts it runs and
  report first attempts and retries separately; it MUST fail if its first attempts exceed
  the plan (an unplanned call), and MUST fail on retries only when all requests together
  exceed twice the plan (a safety cap).
- **FR-019**: The five questions in `eval/probe_notes.md` MUST be run through question
  answering and their answers, citations and verdicts recorded.

### Key Entities

- **Question**: The researcher's text, optional paper filter, optional k, optional
  conversation history.
- **Conversation turn**: One message in the history, with a role (researcher or assistant)
  and text.
- **Numbered passage**: A retrieved passage sent to the model, with its citation
  number (1..n), paper title, section, page, score and text.
- **Answer**: The answer text, the numbered passages, the standalone question (if rewritten),
  citation report (valid and invalid numbers, uncited sentences), whether it is the
  not-found answer, any warning (with the original answer text when it was rejected),
  timings, and token counts when available.
- **Citation report**: The set of cited numbers split into valid and invalid, and the list
  of answer sentences that carry no citation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For an answerable checkpoint question, 100% of citation numbers in the answer
  map to passages in the returned list.
- **SC-002**: "What is the capital of France?" returns exactly the not-found sentence in 100%
  of runs.
- **SC-003**: On the threshold calibration set, no on-topic question is rejected by the
  threshold (hard requirement). Rejecting at least 80% of off-topic questions without
  contacting the language model is a target; if the score ranges overlap, the measured rate
  is recorded and every off-topic question still ends with the not-found sentence (SC-002
  style), either from the threshold or from the language model.
- **SC-004**: 100% of passages in a filtered answer come from the selected paper(s).
- **SC-005**: For the follow-up checkpoint ("What are its limitations?" after a LoRA
  question), the standalone question names LoRA and a reviewer judges the answer relevant.
- **SC-006**: For the five probe questions, a reviewer finds zero claims that are not
  supported by the cited passages; for the two questions whose answers retrieval missed
  (Q2, Q4), the answer is the not-found sentence or a correctly limited partial answer.
- **SC-007**: A search of the repository, logs and error output finds zero occurrences of the
  API key value.
- **SC-008**: In a checkpoint run, the median generate time of answered (non-not-found)
  questions is at most 15 seconds. Generate times of not-found answers and the maximum
  generate time are reported, not checked (free endpoints vary widely; see research R13).
  Each model request is limited by a configurable timeout (default 60 seconds) that ends in a
  readable error.
- **SC-009**: Under a simulated persistent provider failure, 100% of attempts end with a
  readable message and no stack trace.
- **SC-010**: 100% of answers report rewrite, retrieve and generate timings.
- **SC-011**: Answers to the checkpoint and probe questions are at most 165 words (150 plus a
  10% margin), or at most 330 words when the question asks for detail.

## Assumptions

- Feature 1 is complete: the library holds the 5 test papers and its search (including paper
  filters and 0–1 similarity scores) is reused unchanged.
- The researcher has an OpenRouter API key stored in the local, untracked settings file;
  `.env.example` contains placeholders only. Free models allow 20 requests per minute and 50
  per day before $10 of lifetime credits are purchased (1,000 per day after); checkpoint runs
  fit the lower limit, but evaluation runs need the higher one.
- Conversation history is supplied by the caller with each question; this feature does not
  store conversations.
- A "turn" is one message from either the researcher or the assistant, so 6 turns are about
  three exchanges.
- When a question is rewritten, the standalone question is used both for search and as the
  question the answer responds to.
- Retries default to at most 4 attempts; waits follow the provider's retry hint (capped at
  60 seconds) or double from 2 seconds; each provider call has a time limit (default 60
  seconds).
- Answers are in English and returned complete (no streaming).
- Interaction is through Python functions and checkpoint scripts, as in Feature 1.

## Out of Scope

- Summaries and paper comparison.
- Any user interface or network API.
- Streaming answers.
- Providers that are not OpenAI-compatible, and provider-specific features beyond the
  output and reasoning limits.
- The full evaluation harness (only the five probe questions are recorded here).
- Reranking or hybrid keyword + vector search.
