/** Ask and Summary keep their state while the reader visits other pages: the layout's providers
 *  stay mounted while pages come and go (the Compare screen's equivalent is compare-session). */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { StatusProvider } from "@/components/app/StatusGate";
import { UsageProvider } from "@/components/app/UsageMeter";
import { AskProvider } from "@/components/ask/AskProvider";
import { AskScreen } from "@/components/ask/AskScreen";
import { SummaryProvider } from "@/components/summary/SummaryProvider";
import { SummaryView } from "@/components/summary/SummaryView";
import type { Answer, PaperCard } from "@/lib/types";

import { part, summary } from "./summary-fixtures";

vi.mock("react-pdf", () => ({ Document: () => null, Page: () => null, pdfjs: { GlobalWorkerOptions: {} } }));

const encoder = new TextEncoder();

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function controlledStream() {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({ start: (c) => void (controller = c) });
  return {
    response: new Response(body, { headers: { "Content-Type": "text/event-stream" } }),
    send: (event: string, data: unknown) =>
      controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)),
    close: () => controller.close(),
  };
}

const LORA: PaperCard = {
  paper_id: "lora", title: "LoRA: Low-Rank Adaptation", arxiv_id: null, page_count: 26, passage_count: 56,
  text_passages: 50, table_passages: 6, section_count: 8, has_pdf: true, highlights: "exact",
};

function answer(text: string): Answer {
  return {
    question: "q", standalone_question: "q", rewrite_applied: false, rewrite_fallback_reason: null, text, not_found: false,
    fallback_reason: null, warning: null, rejected_answer: null, citations: { valid: [1], invalid: [], uncited_sentences: [] },
    verified: true,
    passages: [{ number: 1, passage_id: "lora-1", paper_id: "lora", title: LORA.title, section: "Method", page: 2, score: 0.7, text: "x" }],
    papers_read: 1, word_count: 6, llm_calls: 1, requests: { planned: 1, retries: 0 },
    timings: { rewrite: 0, retrieve: 0.1, generate: 1 }, tokens: {},
    usage: { used: 34, limit: 50, remaining: 16, resets_at: "2026-10-26T00:00:00Z", source: "provider" },
  };
}

/** Every route the pages use; each POST takes the next queued stream for its path. */
function backend(streams: Record<string, Response[]>, saved: Record<string, unknown> = {}) {
  const posted: Record<string, unknown[]> = {};
  const looked: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: unknown, init: RequestInit = {}) => {
    const path = new URL(String(input)).pathname;
    const method = init.method ?? "GET";
    if (path === "/api/status") return json({ state: "ready", model: "nvidia/x:free", model_is_free: true, daily_limit: 50 });
    if (path === "/api/usage") {
      return json({ used: 9, limit: 50, remaining: 41, resets_at: "2026-10-26T00:00:00Z", source: "provider" });
    }
    if (path === "/api/papers") return json({ papers: [LORA], total_passages: 56 });
    if (path === "/api/summaries" && method === "GET") {
      return json({ papers: [{ paper_id: "lora", title: LORA.title, arxiv_id: null }] });
    }
    if (method === "GET" && path.startsWith("/api/summaries/")) {
      looked.push(path);
      return path in saved ? json(saved[path]) : json({ kind: "not_saved", plan: { max_requests: 6 } }, 404);
    }
    if (method === "POST") {
      (posted[path] ??= []).push(JSON.parse(String(init.body ?? "{}")));
      const next = streams[path]?.shift();
      if (!next) throw new Error(`no stream left for ${path}`);
      return next;
    }
    throw new Error(`Unexpected ${method} ${path}`);
  }));
  return { posted, looked };
}

type Page = "ask" | "summary-lora" | "summary-bert" | "library";

/** The app's layout: providers above the pages, which mount and unmount as the reader navigates. */
function App({ page }: { page: Page }): ReactNode {
  return (
    <StatusProvider>
      <UsageProvider>
        <AskProvider>
          <SummaryProvider>
            {page === "ask" && <AskScreen />}
            {page === "summary-lora" && <SummaryView paperId="lora" />}
            {page === "summary-bert" && <SummaryView paperId="bert" />}
            {page === "library" && <p>The library page</p>}
          </SummaryProvider>
        </AskProvider>
      </UsageProvider>
    </StatusProvider>
  );
}

describe("The Ask screen keeps its conversation across page visits", () => {
  it("finishes an answer that arrives while away, sends no second request, and follows up with history", async () => {
    const first = controlledStream();
    const second = controlledStream();
    const { posted } = backend({ "/api/ask": [first.response, second.response] });
    const user = userEvent.setup();
    const { rerender } = render(<App page="ask" />);
    await user.type(await screen.findByRole("textbox", { name: /ask about your papers/i }), "What is LoRA?{Enter}");
    await waitFor(() => expect(posted["/api/ask"]).toHaveLength(1));

    rerender(<App page="library" />);
    first.send("answer", answer("LoRA trains low-rank update matrices [1]."));
    first.close();
    rerender(<App page="ask" />);

    expect(await screen.findByText(/LoRA trains low-rank update matrices/)).toBeInTheDocument();
    expect(screen.getByText("What is LoRA?")).toBeInTheDocument();
    expect(posted["/api/ask"]).toHaveLength(1);

    await user.type(screen.getByRole("textbox", { name: /ask about your papers/i }), "How many parameters does it save?{Enter}");
    await waitFor(() => expect(posted["/api/ask"]).toHaveLength(2));
    expect((posted["/api/ask"]![1] as { history?: unknown[] }).history).toHaveLength(2);
  });

  it("keeps an unsent question in the box", async () => {
    backend({});
    const user = userEvent.setup();
    const { rerender } = render(<App page="ask" />);
    await user.type(await screen.findByRole("textbox", { name: /ask about your papers/i }), "Half-written question");
    rerender(<App page="library" />);
    rerender(<App page="ask" />);
    expect(await screen.findByRole("textbox", { name: /ask about your papers/i })).toHaveValue("Half-written question");
  });
});

describe("A summary keeps running and stays shown across page visits", () => {
  it("shows the parts that arrived while away and the finished summary, with one request", async () => {
    const run = controlledStream();
    const { posted } = backend({ "/api/summaries/lora": [run.response] });
    const user = userEvent.setup();
    const { rerender } = render(<App page="summary-lora" />);
    await user.click(await screen.findByRole("button", { name: "Summarize this paper" }));
    await waitFor(() => expect(posted["/api/summaries/lora"]).toHaveLength(1));
    run.send("progress", { part: "method", step: "generating" });
    expect(await screen.findByText("Writing method")).toBeInTheDocument();

    rerender(<App page="library" />);
    run.send("part", part("method"));

    rerender(<App page="summary-lora" />);
    expect(await screen.findByText(/The method of LoRA is stated here/)).toBeInTheDocument();
    run.send("summary", summary());
    run.close();
    expect(await screen.findByText(/LoRA freezes the model/)).toBeInTheDocument();
    expect(posted["/api/summaries/lora"]).toHaveLength(1);
  });

  it("keeps each paper's summary separately and does not look a finished one up again", async () => {
    const { looked } = backend({}, { "/api/summaries/lora": { ...summary(), plan: { max_requests: 6 } } });
    const { rerender } = render(<App page="summary-lora" />);
    expect(await screen.findByText(/LoRA freezes the model/)).toBeInTheDocument();
    rerender(<App page="summary-bert" />);
    expect(await screen.findByRole("button", { name: "Summarize this paper" })).toBeInTheDocument();
    rerender(<App page="summary-lora" />);
    expect(await screen.findByText(/LoRA freezes the model/)).toBeInTheDocument();
    expect(looked.filter((p) => p === "/api/summaries/lora")).toHaveLength(1);
  });
});
