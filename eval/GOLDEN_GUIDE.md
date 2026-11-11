# Writing the golden set

`eval/golden.json` is the fixed question set every retrieval and answer experiment is measured on
(Feature 5). You write the questions; evidence phrases are drafted afterwards for you to confirm.
Check your work at any time with `python -m evaluation check --drafts` (0 model requests).

## Target counts (36 questions)

| Kind | `kind` | Target | What it tests |
|---|---|---|---|
| Single-paper | `single` | 20: 4 per paper, at least 1 per paper with its answer in a **table** (`"table": true`) | retrieval and a cited answer from one paper |
| Cross-paper | `cross` | 5 | evidence from two or more papers, each needed |
| Near-miss | `near_miss` | 4 | the right topic but not in the papers; expects not-found |
| Off-topic | `off_topic` | 3 | nothing to do with the papers; expects not-found |
| Follow-up | `follow_up` | 4 | a question that only makes sense after earlier turns |

The papers, by arXiv ID: `1706.03762` Attention, `1810.04805` BERT, `2005.11401` RAG, `2106.09685`
LoRA, `2307.03172` Lost in the Middle.

## Fields

| Field | Needed | Notes |
|---|---|---|
| `id` | always | short and stable, e.g. `bert-03`; never reuse one |
| `kind` | always | one of the five above |
| `question` | always | as a researcher would type it |
| `scope` | always | `library` (searched across the 5 papers, the usual case) or `paper` (filtered to its one paper, like choosing a paper in Ask) |
| `papers` | always | the paper(s) the answer comes from; empty for off-topic |
| `expected` | always | the answer in one sentence, or `"not_found"` for near-miss and off-topic |
| `table` | always | `true` when the answer is a value in a table |
| `turns` | follow-ups | the earlier conversation, `[{"role": "user" or "assistant", "text": ...}]` |
| `standalone` | follow-ups | the follow-up rewritten as one self-contained question (used by free retrieval runs) |
| `known_case` | optional | `F1`, `F2`, `Q2` or `Q4` for the recorded cases below |
| `evidence` | leave `[]` | drafted later as `{"paper", "page", "phrase"}`, then confirmed by you |
| `confirmed` | leave `false` | you set `true` once you have checked the evidence against the PDF |
| `note` | optional | where the question came from, or anything worth remembering |

## Good questions

- **Vary the wording** from the paper's own, so the set doesn't only reward copying words; keep a
  few that use the paper's exact terms, since researchers do both.
- **Near-misses** should sound answerable: a related model, a different version or a detail the
  paper never gives ("What GPU did they train on?" when it doesn't say). The probe's ones are good
  models: "How was GPT-4 trained?", "What is the context window of Claude 3?".
- **Table answers** are where numbers are most often misread (F3), so make them precise: one cell, named
  by its row and column.
- **Known cases** (`eval/probe_notes.md`), to include with `known_case`:
  - **F1:** "How does that method reduce the number of trainable parameters?" (a LoRA follow-up)
  - **F2:** "What is LoRA?"
  - **Q2:** "What are the two pre-training tasks of BERT?"
  - **Q4:** "What rank r does LoRA use for GPT-3?"

## Why there are no passage IDs

A passage ID (`a8ca46b17146-34`) is a position in a paper's chunking, and changes whenever chunking does.
The set records each piece of evidence as a phrase copied from the paper with its page. The check finds
the phrase in the stored passages by text, so the set stays valid after re-chunking, and the prefix
experiment's separate library reads it the same way.

## After you have written the questions

1. **Evidence is drafted** (task T017): one or two phrases per answerable question, copied from the PDF
   with the page, each checked to match a stored passage (a table passage for `table: true`). A question
   whose answer can't be found is listed for you, not given invented evidence.
2. **You confirm each phrase and page against the PDF** (T018), correct any, set `"confirmed": true`, and
   set `"version": 1`.
3. **`python -m evaluation check`** must then pass with no `--drafts` (T019).
