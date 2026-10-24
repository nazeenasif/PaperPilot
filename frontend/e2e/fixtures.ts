// Recorded-shape API responses for the smoke tests (contracts/web-api.md). No PDFs are
// committed (constitution VI): the viewer fixture PDF is built in code (see pdf.ts).

import type { Answer, Status } from "../lib/types";

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

export const ASK_EVENTS: [string, unknown][] = [
  ["progress", { step: "searching" }],
  ["progress", { step: "reading", passages: 2, papers: 1 }],
  ["progress", { step: "generating" }],
  ["progress", { step: "checking" }],
  ["answer", ANSWER],
];
