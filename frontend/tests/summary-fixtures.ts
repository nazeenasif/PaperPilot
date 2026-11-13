// Shared summary fixtures for the Vitest suites (not a test file).

import type { NumberedPassage, Part, Summary } from "@/lib/types";

const FACETS = ["problem", "method", "data", "results", "limitations"] as const;
const PAPER = "lora";

export const PASSAGES: NumberedPassage[] = [1, 2, 3, 4, 5].map((n) => ({
  number: n,
  passage_id: `lora-${n}`,
  paper_id: PAPER,
  title: "LoRA: Low-Rank Adaptation of Large Language Models",
  section: "Method",
  page: n + 1,
  score: 0.7,
  text: `Passage ${n} text.`,
}));

export function part(name: string, overrides: Partial<Part> = {}): Part {
  return {
    part: name,
    state: "verified",
    text: `The ${name} of LoRA is stated here [1].`,
    citations: { valid: [1], invalid: [], uncited_sentences: [] },
    warning: null,
    rejected_text: null,
    reason: null,
    sources: name === "tldr" ? [["Problem"]] : [],
    built_from: name === "tldr" ? [...FACETS] : [],
    built_without: [],
    passages: [1, 2, 3, 4],
    requests: { planned: 1, retries: 0 },
    tokens: { input: 900, output: 120, reasoning: 300 },
    ...overrides,
  };
}

export function summary(overrides: Partial<Summary> = {}): Summary {
  return {
    paper_id: PAPER,
    title: "LoRA: Low-Rank Adaptation of Large Language Models",
    arxiv_id: "2106.09685",
    tldr: part("tldr", { text: "LoRA freezes the model and trains small matrices [1]." }),
    sections: FACETS.map((f) => part(f)),
    passages: PASSAGES,
    plan: { max_requests: 6 },
    requests: { planned: 6, retries: 0 },
    model: "nvidia/nemotron-3-ultra-550b-a55b:free",
    prompt_version: 1,
    created_at: "2026-10-25T10:00:00+00:00",
    status: "current",
    stale_reason: null,
    verified_parts: 6,
    ...overrides,
  };
}
