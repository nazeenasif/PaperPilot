// Recorded-shape API responses for the smoke tests (contracts/web-api.md). No PDFs are
// committed (constitution VI): the viewer fixture PDF is built in code (see pdf.ts).

import type { Answer, PaperCard, PassageView, Status, UploadJob, Usage } from "../lib/types";

export const STATUS: Status = {
  state: "ready",
  model: "nvidia/nemotron-3-ultra-550b-a55b:free",
  model_is_free: true,
  daily_limit: 50,
};

export const PASSAGES: Answer["passages"] = [
  {
    number: 1,
    passage_id: "lora-12",
    paper_id: "lora",
    title: "LoRA: Low-Rank Adaptation of Large Language Models",
    section: "Our Method",
    page: 1,
    score: 0.741,
    text: "LoRA freezes the pretrained weights and injects trainable rank decomposition matrices.",
  },
  {
    number: 2,
    passage_id: "lora-30",
    paper_id: "lora",
    title: "LoRA: Low-Rank Adaptation of Large Language Models",
    section: "Conclusion",
    page: 1,
    score: 0.702,
    text: "LoRA allows quick task switching when deployed as a service.",
  },
];

export const ANSWER: Answer = {
  question: "What is LoRA?",
  standalone_question: "What is LoRA?",
  rewrite_applied: false,
  rewrite_fallback_reason: null,
  text: "LoRA is an efficient adaptation strategy that freezes the pretrained weights [1]. It allows quick task switching when deployed as a service [2].",
  not_found: false,
  fallback_reason: null,
  warning: null,
  rejected_answer: null,
  citations: { valid: [1, 2], invalid: [], uncited_sentences: [] },
  verified: true,
  passages: PASSAGES,
  papers_read: 1,
  word_count: 23,
  llm_calls: 1,
  requests: { planned: 1, retries: 0 },
  timings: { rewrite: 0, retrieve: 0.1, generate: 8.7 },
  tokens: {},
  usage: null as unknown as Answer["usage"],
};

export const PDF_LINES = [
  "LoRA freezes the pretrained weights and injects",
  "trainable rank decomposition matrices into each layer.",
  "LoRA allows quick task switching when deployed as a service.",
];

/** Passage 1: highlighted on page 1 (regions in points, origin top-left: first text line at y≈80). */
export const VIEW_HIGHLIGHTED: PassageView = {
  passage_id: "lora-12",
  paper_id: "lora",
  title: PASSAGES[0]!.title,
  section: "Our Method",
  page: 1,
  page_count: 1,
  kind: "text",
  text: PASSAGES[0]!.text,
  has_pdf: true,
  layout: {
    pages: [{ number: 1, width: 612, height: 792 }],
    regions: [
      { page: 1, x0: 72, y0: 69, x1: 340, y1: 83 },
      { page: 1, x0: 72, y0: 85, x1: 370, y1: 99 },
    ],
  },
  layout_reason: null,
  can_reprocess: false,
};

/** Passage 2: the exact location could not be marked, so its text is shown beside the page. */
export const VIEW_UNMARKED: PassageView = {
  ...VIEW_HIGHLIGHTED,
  passage_id: "lora-30",
  section: "Conclusion",
  text: PASSAGES[1]!.text,
  layout: null,
  layout_reason: "unavailable",
};

export const ASK_EVENTS: [string, unknown][] = [
  ["progress", { step: "searching" }],
  ["progress", { step: "reading", passages: 2, papers: 1 }],
  ["progress", { step: "generating" }],
  ["progress", { step: "checking" }],
  ["answer", ANSWER],
];

// --- Library (US3) ---

export const LIBRARY_PAPERS: PaperCard[] = [
  {
    paper_id: "att",
    title: "Attention Is All You Need",
    page_count: 15,
    passage_count: 33,
    text_passages: 29,
    table_passages: 4,
    section_count: 8,
    arxiv_id: "1706.03762",
    has_pdf: false,
    highlights: "no_pdf",
  },
  {
    paper_id: "bert",
    title: "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
    page_count: 16,
    passage_count: 42,
    text_passages: 36,
    table_passages: 6,
    section_count: 7,
    arxiv_id: "1810.04805",
    has_pdf: true,
    highlights: "exact",
  },
];

export const NEW_PAPER: PaperCard = {
  paper_id: "new",
  title: "A Small Study of Grounded Answers",
  page_count: 1,
  passage_count: 3,
  text_passages: 3,
  table_passages: 0,
  section_count: 2,
  arxiv_id: null,
  has_pdf: true,
  highlights: "exact",
};

/** What each successive GET /api/jobs shows for a job, by file name, after it is uploaded. */
export const JOB_SCRIPTS: Record<string, Partial<UploadJob>[]> = {
  "new-paper.pdf": [
    { phase: "queued" },
    { phase: "parsing" },
    { phase: "chunking" },
    { phase: "embedding", percent: 40 },
    { phase: "embedding", percent: 80 },
    { phase: "ready", outcome: "added", highlights: "exact", paper_id: "new" },
  ],
  "attention.pdf": [
    { phase: "queued" },
    { phase: "mapping", paper_id: "att" },
    { phase: "mapping", paper_id: "att" },
    { phase: "ready", outcome: "pdf_attached", highlights: "exact", paper_id: "att" },
  ],
  "bert renamed.pdf": [{ phase: "ready", outcome: "already_present", highlights: "exact", paper_id: "bert" }],
};

// --- Failure states (US5) ---

export const USAGE: Usage = { used: 34, limit: 50, remaining: 16, resets_at: "2026-10-26T00:00:00Z", source: "provider" };

export const NOT_FOUND_TEXT = "I couldn't find that in the selected papers.";

export const NOT_FOUND_ANSWER: Answer = {
  ...ANSWER,
  text: NOT_FOUND_TEXT,
  not_found: true,
  verified: false,
  fallback_reason: "below_threshold",
  passages: [],
  citations: { valid: [], invalid: [], uncited_sentences: [] },
};

export const HELD_BACK_ANSWER: Answer = {
  ...ANSWER,
  text: NOT_FOUND_TEXT,
  not_found: true,
  verified: false,
  fallback_reason: "invalid_citations",
  rejected_answer: "LoRA trains low-rank update matrices [7].",
  warning: "server wording",
  citations: { valid: [], invalid: [7], uncited_sentences: [] },
};

export const SEARCH_RESULTS = {
  results: [
    {
      rank: 1,
      score: 0.74,
      passage_id: "lora-12",
      paper_id: "lora",
      title: "LoRA: Low-Rank Adaptation of Large Language Models",
      section: "Our Method",
      page: 1,
      text: "LoRA freezes the pretrained weights and injects trainable rank decomposition matrices.",
    },
  ],
};
