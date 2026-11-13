import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StatusProvider } from "@/components/app/StatusGate";
import { UsageProvider } from "@/components/app/UsageMeter";
import { ComparisonProvider } from "@/components/compare/ComparisonProvider";
import { CompareView } from "@/components/compare/CompareView";
import type { Comparison, PaperCard } from "@/lib/types";

import { PASSAGES, part } from "./summary-fixtures";

vi.mock("react-pdf", () => ({ Document: () => null, Page: () => null, pdfjs: { GlobalWorkerOptions: {} } }));

const encoder = new TextEncoder();

function paper(paper_id: string, title: string): PaperCard {
  return { paper_id, title, arxiv_id: null, page_count: 10, passage_count: 40, text_passages: 35, table_passages: 5,
           section_count: 6, has_pdf: true, highlights: "exact" };
}

const PAPERS = [paper("bert", "BERT: Pre-training"), paper("rag", "Retrieval-Augmented Generation"), paper("lora", "LoRA")];

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function comparison(): Comparison {
  const rows = (["method", "results"] as const).map((aspect) => ({
    aspect, state: "ok" as const, reason: null, until: null, tokens: {},
    cells: [part(`${aspect}:bert`, { text: `BERT ${aspect} claim [1].`, passages: [1] }),
            part(`${aspect}:rag`, { text: `RAG ${aspect} claim [2].`, passages: [2] })],
  }));
  return {
    paper_ids: ["bert", "rag"],
    papers: [{ paper_id: "bert", title: "BERT: Pre-training", arxiv_id: null, label: "P1" },
             { paper_id: "rag", title: "Retrieval-Augmented Generation", arxiv_id: null, label: "P2" }],
    aspects: ["method", "results"], rows, passages: PASSAGES, plan: { max_requests: 2, parts: ["method", "results"] },
    requests: { planned: 2, retries: 0 }, model: "nvidia/x:free", prompt_version: 8, created_at: new Date().toISOString(),
    status: "current", stale_reason: null, verified_cells: 4, total_cells: 4, pending: null,
  };
}

function controlledStream() {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({ start: (c) => void (controller = c) });
  return {
    response: new Response(body, { headers: { "Content-Type": "text/event-stream" } }),
    send: (event: string, data: unknown) => controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)),
    close: () => controller.close(),
  };
}

function backend(posts: Response[] = [], saved: Comparison | null = null) {
  const posted: unknown[] = [];
  const looked: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: unknown, init: RequestInit = {}) => {
    const url = new URL(String(input));
    const method = init.method ?? "GET";
    if (url.pathname === "/api/status") return json({ state: "ready", model: "nvidia/x:free", model_is_free: true, daily_limit: 50 });
    if (url.pathname === "/api/usage") return json({ used: 9, limit: 50, remaining: 41, resets_at: "2026-11-09T00:00:00Z", source: "local" });
    if (url.pathname === "/api/papers") return json({ papers: PAPERS });
    if (url.pathname === "/api/comparisons" && method === "GET") {
      looked.push(url.search);
      return saved ? json(saved) : json({ kind: "not_saved", plan: { max_requests: 2 } }, 404);
    }
    if (url.pathname === "/api/comparisons" && method === "POST") {
      posted.push(JSON.parse(String(init.body)));
      const next = posts.shift();
      if (!next) throw new Error("no stream left");
      return next;
    }
    throw new Error(`Unexpected ${method} ${url.pathname}`);
  }));
  return { posted, looked };
}

/** The app's layout: the providers stay mounted while pages come and go. */
function App({ page }: { page: "compare" | "library" }): ReactNode {
  return (
    <StatusProvider>
      <UsageProvider>
        <ComparisonProvider>{page === "compare" ? <CompareView /> : <p>The library page</p>}</ComparisonProvider>
      </UsageProvider>
    </StatusProvider>
  );
}

afterEach(() => {
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe("A comparison survives leaving the Compare page", () => {
  it("keeps the papers and the running comparison, and sends no second request", async () => {
    const stream = controlledStream();
    const { posted } = backend([stream.response]);
    const user = userEvent.setup();
    const { rerender } = render(<App page="compare" />);
    for (const title of ["BERT: Pre-training", "Retrieval-Augmented Generation"]) {
      await user.selectOptions(await screen.findByRole("combobox", { name: "Add paper" }), title);
    }
    for (const name of ["Problem", "Datasets", "Limitations"]) await user.click(await screen.findByRole("checkbox", { name }));
    await user.click(await screen.findByRole("button", { name: "Compare papers" }));
    await waitFor(() => expect(posted).toHaveLength(1));
    stream.send("progress", { part: "method", step: "generating" });
    expect(await screen.findByText("Writing method")).toBeInTheDocument();

    rerender(<App page="library" />);
    expect(screen.getByText("The library page")).toBeInTheDocument();
    stream.send("part", part("method:bert", { text: "BERT method claim [1].", passages: [1] }));

    rerender(<App page="compare" />);
    expect(await screen.findByRole("button", { name: "Remove BERT: Pre-training" })).toBeInTheDocument();
    expect(await screen.findByText(/BERT method claim/)).toBeInTheDocument();
    expect(screen.getByText("Writing method")).toBeInTheDocument();

    stream.send("comparison", comparison());
    stream.close();
    expect(await screen.findByText(/4 of 4 cells verified/)).toBeInTheDocument();
    expect(posted).toHaveLength(1);
  });

  it("keeps a finished comparison on screen after leaving and coming back", async () => {
    const { looked } = backend([], comparison());
    const user = userEvent.setup();
    const { rerender } = render(<App page="compare" />);
    for (const title of ["BERT: Pre-training", "Retrieval-Augmented Generation"]) {
      await user.selectOptions(await screen.findByRole("combobox", { name: "Add paper" }), title);
    }
    expect(await screen.findByText(/4 of 4 cells verified/)).toBeInTheDocument();
    rerender(<App page="library" />);
    rerender(<App page="compare" />);
    expect(await screen.findByText(/4 of 4 cells verified/)).toBeInTheDocument();
    expect(looked).toHaveLength(1); // shown from memory, not looked up again
  });

  it("remembers the chosen papers and aspects after a reload, and opens their saved comparison", async () => {
    window.sessionStorage.setItem("paperpilot.compare", JSON.stringify({ papers: ["bert", "rag"], aspects: ["method", "results"] }));
    const { looked } = backend([], comparison());
    render(<App page="compare" />);
    expect(await screen.findByRole("button", { name: "Remove BERT: Pre-training" })).toBeInTheDocument();
    expect(await screen.findByText(/4 of 4 cells verified/)).toBeInTheDocument();
    expect(looked[0]).toContain("papers=bert%2Crag");
    expect(looked[0]).toContain("aspects=method%2Cresults");
  });
});
