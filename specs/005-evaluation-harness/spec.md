# Feature Specification: Evaluation Harness

**Feature Branch**: `005-evaluation-harness`  
**Created**: 2026-11-11  
**Status**: Draft  
**Input**: User description: "Feature 5: Evaluation harness for PaperPilot (see docs/paperpilot-guide.pdf, Phases 11–12). Goal: measure retrieval and answer quality on a fixed golden set, so every change is judged by numbers, and produce the results table for the README. User stories: 1. As the developer, I maintain a golden set of 30–50 questions over the 5 papers: answerable single-paper questions, cross-paper questions, near-miss and off-topic questions (expected: not-found), and multi-turn follow-ups. Each answerable question records its expected answer and evidence phrase(s) with paper and page, never passage IDs (IDs change when chunking changes). 2. As the developer, I run retrieval evaluation (hit@k, MRR) with zero model requests, for any retrieval configuration. 3. As the developer, I run answer evaluation: each answer is checked for citation validity, correct refusal, and faithfulness by an LLM judge; answers and judge verdicts are cached so re-running the judge or the report costs nothing. 4. As the developer, I trust the judge because it is calibrated against my own hand verdicts (docs/verification reports and eval/probe_notes.md cases F1, F2, F3), with agreement reported, and every judge verdict shows the claim and passage it judged. 5. As the developer, I run experiments one variable at a time and get one row per experiment in a results table (hit@6, MRR, faithfulness, correct refusals, latency, requests), with a written takeaway. Requirements: Experiments to support: baseline; cross-encoder reranking of the top 20 (local, free); hybrid BM25 + vector; title/section prefix before embedding; the scope rule on/off; LLM_REASONING_EFFORT low vs default; a second model (google/gemma-4-31b-it:free). The known cases are fixed test items: F1 (misattribution), F2 (scope extension, 4+ occurrences), F3 (wrong-item number, 3 runs), Q2/Q4 false not-founds, the LoRA/BERT summary and comparison flags. Request budget: every run plans its requests up front, refuses to start without enough remaining, and can resume across days; retrieval-only runs cost 0. The judge should be a different model from the answerer where possible, to avoid self-grading. The judge sees only the claim and its cited passages, and outputs structured verdicts (supported / partly / unsupported, with the reason). Results are stored per experiment with the exact configuration (model, prompt versions, chunking, retrieval settings), so rows are reproducible. Out of scope: new user-facing features, RAGAS integration, fine-tuning. Acceptance criteria (guide Checkpoint 11): A golden set with a baseline row and at least two experiments with written conclusions. Judge agreement with my hand verdicts is reported, with disagreements listed. The README results table is generated from stored results, not typed by hand."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A golden set that survives re-chunking (Priority: P1)

The developer keeps a fixed set of 30–50 questions over the 5 papers, of known kinds: answerable
questions about one paper, questions across papers, near-miss and off-topic questions that should get
"not found", and multi-turn follow-ups. An answerable question records its expected answer and the
evidence phrases that prove it, each with its paper and page, and never a passage ID, so the set stays
valid when chunking changes. A check confirms every evidence phrase really is on its stated page.

**Why this priority**: every number in this feature is measured against this set; without it nothing
else means anything.

**Independent Test**: run the golden-set check with no model requests; confirm it reports the count per
question kind and fails for a deliberately wrong page or a phrase that is not in the paper.

**Acceptance Scenarios**:

1. **Given** the golden set, **When** the check runs, **Then** it reports the number of questions per
   kind and confirms the set has 30–50 questions over all 5 papers, with no model requests.
2. **Given** an evidence phrase that is not on its stated page, or an unknown paper, **When** the check
   runs, **Then** it names that question and fails.
3. **Given** a golden item containing a passage ID, **When** the check runs, **Then** it fails.
4. **Given** chunking settings are changed, **When** the check runs again, **Then** the golden set is
   still valid, unchanged.

---

### User Story 2 - Retrieval quality at no cost (Priority: P1)

The developer measures retrieval for any retrieval configuration, getting hit@k and MRR with zero model
requests. An experiment that changes chunking, embedding text or ranking is measured on its own copy of
the passages and leaves the researcher's library as it was.

**Why this priority**: retrieval is free to measure and is where the known false not-founds begin; it
gives usable numbers before any request is spent.

**Independent Test**: run the baseline retrieval evaluation; confirm hit@6 and MRR, a per-question list
of the rank at which the evidence was found, a request count of 0, and an unchanged library.

**Acceptance Scenarios**:

1. **Given** the golden set, **When** retrieval evaluation runs, **Then** it reports hit@k for the chosen
   k and MRR over the answerable questions, and the rank of the evidence for each one, with 0 model requests.
2. **Given** a question whose evidence spans two papers, **When** it is scored, **Then** it counts as a
   hit only when evidence from every required paper is in the top k.
3. **Given** a multi-turn follow-up, **When** retrieval evaluation runs, **Then** it uses that follow-up's
   recorded standalone wording, so it still costs 0 requests.
4. **Given** a configuration that alters chunking or the embedded text, **When** it runs, **Then** the
   library's passages, and saved summaries and comparisons, are unchanged afterwards.
5. **Given** the same configuration run twice, **Then** the numbers are identical.

---

### User Story 3 - Answer quality, cached (Priority: P1)

The developer runs answer evaluation. Each answer is checked in code for citation validity and correct
refusal, and its claims are judged for faithfulness by a language model. Answers and verdicts are kept,
so re-running the judge on stored answers, or the report, repeats no request that has already been made.

**Why this priority**: faithfulness is what citation checks cannot see (F1, F2, F3); it is the point
of the harness.

**Independent Test**: run answer evaluation on a few questions with a scripted model; run it again and
confirm 0 further requests and identical results; change only the judge's version and confirm only
judge requests are made.

**Acceptance Scenarios**:

1. **Given** an answerable question, **When** it is evaluated, **Then** its citation validity, whether it
   wrongly said not-found, and a verdict for each of its claims are recorded.
2. **Given** an unanswerable question, **When** it is evaluated, **Then** it is scored on whether it said
   not-found, and no judge request is made for a correct refusal.
3. **Given** stored answers and verdicts, **When** the evaluation or report is run again, **Then** no
   model request is made and the numbers are identical.
4. **Given** a changed judge or judge instruction, **When** evaluation runs, **Then** stored answers are
   reused and only the verdicts are redone.
5. **Given** a changed answer configuration, **Then** answers made under another configuration are not reused.
6. **Given** a sentence with no citation, **Then** no judge request is made for it and it is counted separately.
7. **Given** a judge reply that cannot be read or is cut off, **Then** that claim is "not judged", is
   reported as such and retried on a later run, and is never counted as supported.

---

### User Story 4 - A judge that has earned trust (Priority: P2)

Before its numbers are used, the judge is run against claims whose correct verdict the developer already
knows by hand: the recorded failure cases and hand-checked claims from the verification reports. Its
agreement is reported, every disagreement is listed, and every verdict anywhere can be traced to the
claim and passages it judged.

**Why this priority**: an unmeasured judge only moves the doubt somewhere else, but this needs a working
judge and hand verdicts first.

**Independent Test**: run calibration over the stored cases; confirm an agreement figure, a list of
disagreements with the claim, passages, hand verdict, judge verdict and reason, and a re-run that costs 0.

**Acceptance Scenarios**:

1. **Given** the calibration set, **When** calibration runs, **Then** it reports overall agreement and
   agreement for claims the developer marked supported and for those marked otherwise.
2. **Given** a disagreement, **Then** it is listed with the claim, its passages, both verdicts and the
   judge's reason.
3. **Given** the calibration set is missing supported claims or has too few hand verdicts, **When**
   calibration runs, **Then** it says so and does not report the judge as calibrated.
4. **Given** any verdict in any run, **Then** the developer can see the exact claim and passages judged.
5. **Given** the judge's request, **Then** it contains only the claim and its cited passages: not the
   question, the expected answer, the other claims' passages or which model wrote the answer.

---

### User Story 5 - One variable at a time, one row each (Priority: P2)

The developer runs named experiments that each change one thing from the baseline, and gets one row per
experiment in a results table with a written takeaway. The README's results table is generated from the
stored results.

**Why this priority**: this is the deliverable: evidence for each change, and the table for the README.

**Independent Test**: run the baseline and two experiments; confirm three rows, each with its stored
configuration and takeaway; regenerate the README table and confirm it matches the stored results.

**Acceptance Scenarios**:

1. **Given** an experiment definition, **When** it differs from the baseline in more than one setting,
   **Then** it is refused, naming the differences.
2. **Given** a finished experiment, **Then** its row shows hit@6, MRR, faithfulness, correct refusals,
   latency, requests and its takeaway, and its exact configuration is stored.
3. **Given** an experiment with no written takeaway, **Then** its row says so and does not count towards acceptance.
4. **Given** the golden set has changed since a row was produced, **Then** the row is marked as measured on
   an earlier golden set.
5. **Given** the stored results, **When** the README table is generated, **Then** every figure comes from
   them, and a second generation changes nothing.

---

### User Story 6 - Runs that fit the free tier (Priority: P2)

Every run states its requests before it starts, refuses to start without enough remaining today, and can
continue another day from where it stopped.

**Why this priority**: an answer experiment needs more requests than one free day allows.

**Independent Test**: with usage set near the limit, confirm a refusal with no request sent; stop a
scripted run midway and confirm the next one continues without repeating finished work.

**Acceptance Scenarios**:

1. **Given** a run, **Then** before any request it shows the requests planned in total, those already done,
   and those for this session.
2. **Given** today's remaining requests, less the reserve, are fewer than this session plans, **Then** it does
   not start and says when requests resume.
3. **Given** a run stopped by the daily limit or a long wait, **When** it is started again later, **Then** it
   continues and repeats no finished answer or verdict.
4. **Given** a retrieval-only run, **Then** it needs no remaining requests and makes none.
5. **Given** no session size is set, **Then** a session uses what remains today after the reserve (default 10),
   and never spends the reserve.

---

### Edge Cases

- The configured judge is the answering model: the row is marked self-graded.
- The second model has been removed from the free list: the run refuses before any request and says why.
- An experiment's configuration cannot be applied (for example a missing reranking model): it fails before any request.
- A passage cited by a claim is missing from the stored answer: the claim is "not judged", never supported.
- A claim mixes supported and unsupported parts: the judge returns "partly", counted apart from both.
- A paper is removed from the library: the golden-set check and any run fail and name it.
- A provider retry during a run counts towards the run's requests, reported separately as for other features.
- A section or cell has one citation group at the end of a paragraph: its earlier sentences count as uncited.

## Requirements *(mandatory)*

### Functional Requirements

**Golden set (User Story 1)**

- **FR-001**: The golden set MUST hold 30–50 questions over the 5 papers, with at least 25 answerable
  single-paper questions (at least 5 per paper), 4 cross-paper questions, 6 expected-not-found questions
  (near-miss and off-topic) and 3 multi-turn follow-ups.
- **FR-002**: Each answerable question MUST record an expected answer and at least one evidence phrase, with
  paper and page; a golden item MUST NOT contain a passage ID.
- **FR-003**: Each multi-turn item MUST record its earlier turns and a standalone wording of the follow-up.
- **FR-004**: A check MUST confirm, with no model requests, the composition in FR-001 and that each evidence
  phrase is on its stated page, tolerating PDF ligatures, hyphenation and spacing, and MUST name each failure.
- **FR-005**: The golden set MUST include the known cases as fixed items: the questions behind F1 and F2, and
  the Q2 and Q4 false not-founds.

**Retrieval evaluation (User Story 2)**

- **FR-006**: Retrieval evaluation MUST report hit@k for a chosen k (default 6) and MRR over answerable
  questions, with the evidence rank for each question, and MUST make no model requests.
- **FR-007**: A retrieved passage MUST count as relevant only if it belongs to the required paper and contains
  an evidence phrase; a cross-paper question MUST need evidence from every required paper within k.
- **FR-008**: Retrieval evaluation MUST accept any supported retrieval configuration, and MUST NOT change the
  researcher's library, its passages or saved results.

**Answer evaluation (User Stories 3 and 6)**

- **FR-009**: Answers MUST be produced by PaperPilot's real answer pipeline under the experiment's configuration.
- **FR-010**: Each answer MUST be scored for citation validity, correct refusal on unanswerable questions and
  false not-found on answerable ones.
- **FR-011**: Claims MUST be the sentences found by the existing validator's sentence rule. A claim with no
  citation MUST NOT be sent to the judge; it MUST be reported as uncited and count against faithfulness.
- **FR-012**: A judge request MUST contain only claims and their own cited passages, with passage text treated
  as data, and MUST return for each claim one of supported, partly or unsupported, with a reason. Calibration
  MUST make one request per claim. Experiments MUST make one request per answer (or per summary part or comparison
  row), listing each claim beside only its own cited passages and returning one verdict per claim.
- **FR-013**: The judge MUST be a different model from the answerer whenever one is available; otherwise the
  results MUST be marked self-graded.
- **FR-014**: Faithfulness MUST be reported as the share of claims judged supported, with partly, unsupported,
  uncited and not-judged counts shown; a claim that could not be judged MUST NOT count as supported.
- **FR-015**: Answers MUST be stored against their exact configuration, and verdicts against the claim, its
  passages, the judge model and the judge instruction version; repeating a stored step MUST make no request.
- **FR-016**: Every verdict MUST be traceable to the claim, passages, verdict and reason.

**Request budget (User Story 6)**

- **FR-017**: Before any request, a run MUST show the requests planned in total, already done and for this session.
- **FR-018**: Each session MUST use a configurable slice of the daily quota and MUST keep a reserve for normal
  use (default 10 requests). With no slice set, a session MUST plan what remains today after the reserve, up to the
  work left. A session MUST NOT start when today's remaining requests, less the reserve, are fewer than it plans,
  and MUST say when requests resume.
- **FR-019**: A run stopped by the daily limit, a long wait or the session size MUST resume without repeating
  finished work. All requests MUST count in the shared daily counter, with retries reported separately.

**Judge calibration (User Story 4)**

- **FR-020**: Calibration MUST use stored claims with their passages and a hand verdict, so that it stays valid
  when chunking changes. It MUST include the F1, F2 and F3 cases and the LoRA and BERT–RAG summary and comparison flags.
- **FR-021**: Calibration MUST report overall agreement, agreement per hand verdict, and every disagreement.
- **FR-022**: Calibration MUST need at least 20 hand verdicts with at least 8 supported and 8 not supported, and
  MUST report the judge as not calibrated otherwise, because the recorded failure cases alone would reward a
  judge that always says unsupported.

**Experiments and results (User Story 5)**

- **FR-023**: Each experiment MUST change exactly one setting from the baseline, and MUST be refused otherwise.
- **FR-024**: These experiments MUST be supported: baseline; cross-encoder reranking of the top 20; hybrid
  keyword and vector search; title and section prefix before embedding; the scope rule on and off; reasoning
  effort low against default; and the second model `google/gemma-4-31b-it:free`.
- **FR-024a**: Experiments MUST run in this priority: first the retrieval experiments (reranking, hybrid search,
  prefix), at no model cost; then answer evaluation for only the baseline and the best retrieval configuration.
  Reasoning effort and the second model MUST be optional rows, run only if the budget allows and the developer
  starts them; a row not run MUST NOT block acceptance.
- **FR-024b**: The best retrieval configuration MUST be the retrieval experiment with the highest hit@6, ties broken
  by MRR, and only if it beats the baseline; otherwise answer evaluation runs for the baseline alone. The choice and
  its figures MUST be shown, and the developer MAY override it.
- **FR-025**: The scope-rule experiment MUST be measured on a fixed set, with the rule on and off: the LoRA
  and BERT summaries and the BERT–RAG comparison. It runs there because the rule is in the summary-section, TL;DR
  and comparison-cell instructions and answers to the golden questions never use it.
- **FR-025a**: The rule-on condition MUST reuse an existing saved summary or comparison when its stored
  configuration matches the run's exactly, and MUST generate it otherwise; the row MUST say which outputs were reused.
- **FR-025b**: The scope-rule row and its takeaway MUST state that one run per condition gives an indicative
  result only, because F2 does not occur in every run.
- **FR-026**: Experiment settings MUST apply only to the evaluation: PaperPilot's defaults MUST NOT change unless
  a later change adopts a result.
- **FR-027**: Results MUST be stored per experiment with the exact configuration: model, judge model, prompt
  versions, chunking, retrieval settings, reasoning effort and golden-set version.
- **FR-028**: One row per experiment MUST show hit@6, MRR, faithfulness, correct refusals, latency, requests and
  the takeaway. A retrieval-only row MUST show its answer columns as not measured, never as zero.
- **FR-029**: The README results table MUST be generated from stored results only, repeatably, with the golden set's size and known limits beside it.
- **FR-030**: The harness MUST NOT add user-facing features to the web app.

### Key Entities

- **Golden question**: a question, its kind, the papers it needs, expected answer or expected not-found, evidence phrases with paper and page, and earlier turns with a standalone wording for a follow-up.
- **Experiment**: a named change of one setting from the baseline, with its full configuration and written takeaway.
- **Run**: one experiment's progress: what is planned, done and remaining, across sessions.
- **Stored answer**: an answer with its passages, citations, timing and requests, under one exact configuration.
- **Claim verdict**: a claim, its cited passages, the judge and instruction version, verdict and reason.
- **Calibration item**: a stored claim and passages with the developer's hand verdict and where it came from.
- **Result row**: the metrics of one experiment on one golden-set version, with its takeaway.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A golden set of 30–50 questions meeting FR-001 passes its check, with every evidence phrase confirmed on its page and 0 model requests.
- **SC-002**: A retrieval evaluation of the whole golden set makes 0 model requests and gives identical numbers on a repeat run.
- **SC-003**: Repeating an answer evaluation or report from stored results makes 0 model requests and gives identical numbers.
- **SC-004**: The results table has a baseline row and at least two experiments with written conclusions, each changing exactly one setting.
- **SC-005**: Judge agreement with at least 20 hand verdicts is reported, for supported and not-supported claims separately, with 100% of disagreements listed.
- **SC-006**: The judge flags at least the recorded F2 and F3 cases as partly or unsupported; a case it misses appears as a listed disagreement.
- **SC-007**: With fewer requests remaining after the reserve than a session plans, starting it sends 0 requests; no session spends the reserve; a run stopped midway repeats 0 finished answers or verdicts when resumed.
- **SC-008**: Every figure in the README results table can be traced to a stored result; regenerating it without new results changes nothing.
- **SC-009**: After any experiment, the library's passages, saved summaries and comparisons and PaperPilot's defaults are unchanged.
- **SC-010**: In 100% of scripted tests, a claim that could not be judged is reported as not judged and never counts as supported.

## Clarifications

### Session 2026-11-11

- Q: One judge request per claim, or one per answer? → A: One per claim for calibration; one per answer for experiments (FR-012).
- Q: Which experiments come first, given the free tier? → A: Retrieval experiments first; answer evaluation only for the baseline and the best retrieval configuration; reasoning effort and the second model optional, if budget allows. Each session uses a configurable slice, keeping a reserve (default 10) (FR-018, FR-024a, FR-024b).
- Q: What should the scope-rule experiment run on? → A: The LoRA and BERT summaries and the BERT–RAG comparison, rule on and off, reusing saved rule-on outputs whose stored configuration matches exactly; one run per condition is indicative only (FR-025, FR-025a, FR-025b).

## Assumptions

- **Saved outputs and "exact" configuration**: saved summaries and comparisons record their model, instruction version and passages, but not reasoning effort or output limit. Reuse compares what is recorded and requires the run to use today's default reasoning effort and output limit; the row states that those two were not recorded.
- **Default judge**: `google/gemma-4-31b-it:free` judges the default answering model, and the default model judges when the second model answers, so neither grades itself.
- **Retrieval experiments**: reranking, hybrid search and the prefix are measured for retrieval at no cost. Only the best of them gets answer evaluation (FR-024b); the others' answer columns read "not measured". A retrieval row with a written takeaway counts towards the two experiments the acceptance criteria need.
- **The scope-rule experiment** stays in scope and follows the baseline and best-retrieval answer runs, because it is not an answer evaluation of the golden questions and has its own small fixed set.
- **Hand verdicts**: the Verdict columns of the verification reports are still empty, and `eval/probe_notes.md` records only failures. Calibration needs the developer to fill in hand verdicts, including supported claims, to reach FR-022.
- **Golden authorship**: the developer owns the golden set; drafts are reviewed by the developer before they count.
- **Honest limits**: a self-written set of about 40 questions is small and may favour easy phrasing; the README states this, as the guide asks.
- **Free tier**: about 50 requests a day, shared with normal use and every experiment.
- **The guide's other experiments** (chunk size, overlap, embedding model, k, no query rewriting) are not required here, though the harness can express them as settings.

## Dependencies

- Features 1–4: the library, the answer pipeline, citation validation, the sentence rule, the shared daily request counter and the output limits.
- The developer's hand verdicts (see Assumptions).
- `docs/paperpilot-guide.pdf`, Phases 11–12.

## Out of Scope

- New user-facing features.
- RAGAS integration.
- Fine-tuning.
- Adopting an experiment's winning setting as PaperPilot's default (a separate, later change).
