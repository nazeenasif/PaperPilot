import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AskScreen } from "@/components/ask/AskScreen";
import { SELECTION_KEY } from "@/lib/useScope";
import type { Answer, PaperCard } from "@/lib/types";

const encoder = new TextEncoder();
const NOT_FOUND = "I couldn't find that in the selected papers.";

function paper(paper_id: string, title: string, passage_count: number): PaperCard {
  return { paper_id, title, page_count: 10, passage_count, text_passages: passage_count, table_passages: 0, section_count: 5,
    arxiv_id: null, has_pdf: true, highlights: "exact" };
}

const PAPERS = [
  paper("att", "Attention Is All You Need", 33),
  paper("bert", "BERT: Pre-training of Deep Bidirectional Transformers", 42),
  paper("rag", "Retrieval-Augmented Generation", 44),
  paper("lora", "LoRA: Low-Rank Adaptation", 56),
  paper("lost", "Lost in the Middle", 48),
];

function answer(overrides: Partial<Answer> = {}): Answer {
  return {
    question: "What is LoRA?", standalone_question: "What is LoRA?", rewrite_applied: false, rewrite_fallback_reason: null,
    text: "LoRA adapts large models efficiently [1].", not_found: false, fallback_reason: null, warning: null,
    rejected_answer: null, citations: { valid: [1], invalid: [], uncited_sentences: [] }, verified: true,
    passages: [{ number: 1, passage_id: "lora-1", paper_id: "lora", title: "LoRA: Low-Rank Adaptation", section: "Method", page: 2, score: 0.7, text: "x" }],
    papers_read: 1, word_count: 6, llm_calls: 1, requests: { planned: 1, retries: 0 },
    timings: { rewrite: 0, retrieve: 0.1, generate: 1 }, tokens: {},
    usage: { used: 34, limit: 50, remaining: 16, resets_at: "2026-10-26T00:00:00Z", source: "provider" },
    ...overrides,
  };
}

function streamOf(...events: [string, unknown][]): Response {
  const body = events.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join("");
  return new Response(new ReadableStream({ start: (c) => (c.enqueue(encoder.encode(body)), c.close()) }), {
    headers: { "Content-Type": "text/event-stream" },
  });
}

/** fetch: the library for GET /api/papers; each POST /api/ask gets the next answer. Returns the ask bodies. */
function backend(papers: PaperCard[], ...answers: Answer[]) {
  const asks: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: unknown, init: RequestInit = {}) => {
    const path = new URL(String(input)).pathname;
    if (path === "/api/papers") {
      return new Response(JSON.stringify({ papers, total_passages: papers.reduce((n, p) => n + p.passage_count, 0) }),
        { headers: { "Content-Type": "application/json" } });
    }
    if (path === "/api/ask") {
      asks.push(JSON.parse(String(init.body)));
      return streamOf(["answer", answers[Math.min(asks.length - 1, answers.length - 1)]]);
    }
    throw new Error(`Unexpected ${path}`);
  }));
  return asks;
}

async function send(user: ReturnType<typeof userEvent.setup>, question: string) {
  await user.type(screen.getByRole("textbox", { name: /ask about your papers/i }), `${question}{Enter}`);
}

/** The scope panel beside the conversation (on phones it is in a sheet instead). */
async function panel() {
  return screen.findByRole("region", { name: /search scope/i });
}

beforeEach(() => {
  window.localStorage.clear();
  window.history.replaceState({}, "", "/");
});

afterEach(() => {
  window.localStorage.clear();
  window.history.replaceState({}, "", "/");
});

describe("Scope panel", () => {
  it("lists the papers with checkboxes and passage counts, and counts the selection", async () => {
    backend(PAPERS);
    const user = userEvent.setup();
    render(<AskScreen />);
    const scope = await panel();
    expect(await within(scope).findByRole("checkbox", { name: /Attention Is All You Need/ })).toBeChecked();
    expect(within(scope).getAllByRole("checkbox")).toHaveLength(5);
    expect(within(scope).getByText("56 passages")).toBeInTheDocument();
    expect(scope).toHaveTextContent("Search scope · 5 of 5 papers");
    for (const name of [/Attention/, /Retrieval/, /Lost in the Middle/]) {
      await user.click(within(scope).getByRole("checkbox", { name }));
    }
    expect(scope).toHaveTextContent("Search scope · 2 of 5 papers");
  });

  it("keeps the last selected paper and says why", async () => {
    backend(PAPERS);
    const user = userEvent.setup();
    render(<AskScreen />);
    const scope = await panel();
    await within(scope).findAllByRole("checkbox");
    for (const name of [/Attention/, /BERT/, /Retrieval/, /Lost in the Middle/]) {
      await user.click(within(scope).getByRole("checkbox", { name }));
    }
    const last = within(scope).getByRole("checkbox", { name: /LoRA/ });
    await user.click(last);
    expect(last).toBeChecked();
    expect(within(scope).getByText(/at least one paper must stay selected/i)).toBeInTheDocument();
  });

  it("disables sending when there is no paper to search", async () => {
    backend([]);
    render(<AskScreen />);
    await waitFor(() => expect(screen.getByRole("button", { name: /send question/i })).toBeDisabled());
    expect(screen.getByText(/add a paper in the library first/i)).toBeInTheDocument();
  });

  it("?paper=<id> preselects only that paper, and questions are limited to it", async () => {
    window.history.replaceState({}, "", "/?paper=bert");
    const asks = backend(PAPERS, answer());
    const user = userEvent.setup();
    render(<AskScreen />);
    const scope = await panel();
    expect(await within(scope).findByRole("checkbox", { name: /BERT/ })).toBeChecked();
    expect(within(scope).getByRole("checkbox", { name: /LoRA/ })).not.toBeChecked();
    expect(scope).toHaveTextContent("1 of 5 papers");
    await send(user, "What data was BERT pre-trained on?");
    await waitFor(() => expect(asks).toHaveLength(1));
    expect(asks[0]).toMatchObject({ paper_ids: ["bert"] });
  });

  it("sends no paper_ids when every paper is selected, so new papers are included", async () => {
    const asks = backend(PAPERS, answer());
    const user = userEvent.setup();
    render(<AskScreen />);
    await within(await panel()).findAllByRole("checkbox");
    await send(user, "What is LoRA?");
    await waitFor(() => expect(asks).toHaveLength(1));
    expect(asks[0]).toEqual({ question: "What is LoRA?" });
  });

  it("remembers the selection in localStorage", async () => {
    backend(PAPERS);
    const user = userEvent.setup();
    const { unmount } = render(<AskScreen />);
    await user.click(await within(await panel()).findByRole("checkbox", { name: /Attention/ }));
    expect(JSON.parse(window.localStorage.getItem(SELECTION_KEY) ?? "[]")).toEqual(["bert", "rag", "lora", "lost"]);
    unmount();
    render(<AskScreen />);
    expect(await within(await panel()).findByRole("checkbox", { name: /Attention/ })).not.toBeChecked();
  });

  it("still works when localStorage throws", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    backend(PAPERS);
    const user = userEvent.setup();
    render(<AskScreen />);
    const scope = await panel();
    await user.click(await within(scope).findByRole("checkbox", { name: /Attention/ }));
    expect(scope).toHaveTextContent("4 of 5 papers");
    vi.restoreAllMocks();
  });

  it("opens as an overlay sheet from the Papers button (phone width)", async () => {
    backend(PAPERS);
    const user = userEvent.setup();
    render(<AskScreen />);
    await user.click(await screen.findByRole("button", { name: /choose papers/i }));
    const sheet = await screen.findByRole("dialog");
    expect(within(sheet).getAllByRole("checkbox")).toHaveLength(5);
  });
});

describe("Conversation", () => {
  it("sends the earlier turns as history with a follow-up", async () => {
    const asks = backend(PAPERS, answer(), answer({ question: "What are its limitations?" }));
    const user = userEvent.setup();
    render(<AskScreen />);
    await send(user, "What is LoRA?");
    await screen.findByText(/adapts large models/);
    await send(user, "What are its limitations?");
    await waitFor(() => expect(asks).toHaveLength(2));
    expect(asks[1]).toMatchObject({
      question: "What are its limitations?",
      history: [
        { role: "user", text: "What is LoRA?" },
        { role: "assistant", text: "LoRA adapts large models efficiently [1]." },
      ],
    });
  });

  it("shows what a follow-up was searched as, or that it was searched as typed", async () => {
    backend(PAPERS,
      answer({ question: "What are its limitations?", standalone_question: "What are the limitations of LoRA?", rewrite_applied: true }),
      answer({ question: "And its costs?", standalone_question: "And its costs?", rewrite_fallback_reason: "rewrite_failed" }));
    const user = userEvent.setup();
    render(<AskScreen />);
    await send(user, "What are its limitations?");
    expect(await screen.findByText('Searched as "What are the limitations of LoRA?"')).toBeInTheDocument();
    await send(user, "And its costs?");
    expect(await screen.findByText("Searched as typed")).toBeInTheDocument();
  });

  it("New conversation clears the turns, and the next question has no history", async () => {
    const asks = backend(PAPERS, answer());
    const user = userEvent.setup();
    render(<AskScreen />);
    await send(user, "What is LoRA?");
    await screen.findByText(/adapts large models/);
    await user.click(screen.getByRole("button", { name: /new conversation/i }));
    expect(screen.queryByText(/adapts large models/)).not.toBeInTheDocument();
    await send(user, "What are its limitations?");
    await waitFor(() => expect(asks).toHaveLength(2));
    expect(asks[1]).not.toHaveProperty("history");
  });

  it("Search all papers re-asks with every paper after a scoped not-found", async () => {
    window.history.replaceState({}, "", "/?paper=bert");
    const notFound = answer({ text: NOT_FOUND, not_found: true, verified: false, fallback_reason: "below_threshold", passages: [],
      citations: { valid: [], invalid: [], uncited_sentences: [] } });
    const asks = backend(PAPERS, notFound, answer());
    const user = userEvent.setup();
    render(<AskScreen />);
    await within(await panel()).findAllByRole("checkbox");
    await send(user, "What is LoRA?");
    await user.click(await screen.findByRole("button", { name: "Search all papers" }));
    await waitFor(() => expect(asks).toHaveLength(2));
    expect(asks[1]).toEqual({ question: "What is LoRA?" });
    expect(await panel()).toHaveTextContent("5 of 5 papers");
  });
});
