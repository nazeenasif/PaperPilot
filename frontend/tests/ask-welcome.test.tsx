import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AskScreen } from "@/components/ask/AskScreen";
import { shortTitle, suggestions } from "@/components/ask/AskWelcome";
import type { Answer, PaperCard } from "@/lib/types";

const encoder = new TextEncoder();

function paper(paper_id: string, title: string): PaperCard {
  return { paper_id, title, page_count: 10, passage_count: 40, text_passages: 40, table_passages: 0, section_count: 5,
    arxiv_id: null, has_pdf: true, highlights: "exact" };
}

const PAPERS = [
  paper("lora", "LoRA: Low-Rank Adaptation of Large Language Models"),
  paper("rag", "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"),
  paper("lost", "Lost in the Middle: How Language Models Use Long Contexts"),
];

function answer(): Answer {
  return {
    question: "What is LoRA?", standalone_question: "What is LoRA?", rewrite_applied: false, rewrite_fallback_reason: null,
    text: "LoRA adapts large models efficiently [1].", not_found: false, fallback_reason: null, warning: null,
    rejected_answer: null, citations: { valid: [1], invalid: [], uncited_sentences: [] }, verified: true,
    passages: [{ number: 1, passage_id: "lora-1", paper_id: "lora", title: "LoRA", section: "Method", page: 2, score: 0.7, text: "x" }],
    papers_read: 1, word_count: 6, llm_calls: 1, requests: { planned: 1, retries: 0 },
    timings: { rewrite: 0, retrieve: 0.1, generate: 1 }, tokens: {},
    usage: { used: 34, limit: 50, remaining: 16, resets_at: "2026-10-26T00:00:00Z", source: "provider" },
  };
}

function backend(papers: PaperCard[]) {
  const asks: unknown[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: unknown, init: RequestInit = {}) => {
    const path = new URL(String(input)).pathname;
    if (path === "/api/papers") {
      return new Response(JSON.stringify({ papers, total_passages: 120 }), { headers: { "Content-Type": "application/json" } });
    }
    if (path === "/api/ask") {
      asks.push(JSON.parse(String(init.body)));
      const body = `event: answer\ndata: ${JSON.stringify(answer())}\n\n`;
      return new Response(new ReadableStream({ start: (c) => (c.enqueue(encoder.encode(body)), c.close()) }),
        { headers: { "Content-Type": "text/event-stream" } });
    }
    throw new Error(`Unexpected ${path}`);
  }));
  return asks;
}

beforeEach(() => window.localStorage.clear());
afterEach(() => window.localStorage.clear());

describe("Short titles and suggested questions", () => {
  it("shortens a title at its colon or its first 'for'", () => {
    expect(shortTitle("LoRA: Low-Rank Adaptation of Large Language Models")).toBe("LoRA");
    expect(shortTitle("Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks")).toBe("Retrieval-Augmented Generation");
    expect(shortTitle("Attention Is All You Need")).toBe("Attention Is All You Need");
  });

  it("suggests one question per selected paper, a different kind each, and one across two papers", () => {
    const list = suggestions(PAPERS);
    expect(list).toHaveLength(4);
    expect(list[0]).toContain("LoRA");
    expect(list[1]).toContain("Retrieval-Augmented Generation");
    expect(new Set(list.slice(0, 3).map((q) => q.replace(/LoRA|Retrieval-Augmented Generation|Lost in the Middle/, "X"))).size).toBe(3);
    expect(list[3]).toMatch(/LoRA.*Retrieval-Augmented Generation|Retrieval-Augmented Generation.*LoRA/);
  });

  it("suggests three kinds of question about a single paper", () => {
    const list = suggestions(PAPERS.slice(0, 1));
    expect(list).toHaveLength(3);
    expect(list.every((q) => q.includes("LoRA"))).toBe(true);
  });
});

describe("The Ask screen before the first question", () => {
  it("welcomes the reader, says how many papers are searched, and shows how it works", async () => {
    backend(PAPERS);
    render(<AskScreen />);
    const welcome = await screen.findByRole("region", { name: /ask your papers anything/i });
    expect(await within(welcome).findByText(/only from the 3 selected papers/i)).toBeInTheDocument();
    const steps = within(welcome).getByRole("list", { name: /how it works/i });
    expect(within(steps).getAllByRole("listitem")).toHaveLength(3);
  });

  it("puts a suggested question in the box without sending it", async () => {
    const asks = backend(PAPERS);
    const user = userEvent.setup();
    render(<AskScreen />);
    const first = await screen.findByRole("button", { name: /use this question: .*LoRA/i });
    await user.click(first);
    const box = screen.getByRole("textbox", { name: /ask about your papers/i });
    expect((box as HTMLTextAreaElement).value).toContain("LoRA");
    expect(box).toHaveFocus();
    expect(asks).toHaveLength(0);
    await user.type(box, "{Enter}");
    await waitFor(() => expect(asks).toHaveLength(1));
  });

  it("goes away once a question is asked", async () => {
    backend(PAPERS);
    const user = userEvent.setup();
    render(<AskScreen />);
    await screen.findByRole("region", { name: /ask your papers anything/i });
    await user.type(screen.getByRole("textbox", { name: /ask about your papers/i }), "What is LoRA?{Enter}");
    await screen.findByText(/LoRA adapts large models efficiently/);
    expect(screen.queryByRole("region", { name: /ask your papers anything/i })).toBeNull();
  });

  it("points to the Library when there are no papers", async () => {
    backend([]);
    render(<AskScreen />);
    const link = await screen.findByRole("link", { name: /add a paper/i });
    expect(link).toHaveAttribute("href", "/library");
    expect(screen.queryByRole("button", { name: /use this question/i })).toBeNull();
  });
});
