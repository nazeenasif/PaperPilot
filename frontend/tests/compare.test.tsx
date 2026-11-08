import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { StatusProvider } from "@/components/app/StatusGate";
import { UsageProvider } from "@/components/app/UsageMeter";
import { CompareView } from "@/components/compare/CompareView";
import type { Comparison, ComparisonRow, PaperCard } from "@/lib/types";

import { PASSAGES, part } from "./summary-fixtures";

vi.mock("react-pdf", () => ({ Document: () => null, Page: () => null, pdfjs: { GlobalWorkerOptions: {} } }));

const encoder = new TextEncoder();

function paper(paper_id: string, title: string, arxiv_id: string | null = null): PaperCard {
  return {
    paper_id, title, arxiv_id, page_count: 10, passage_count: 40, text_passages: 35, table_passages: 5, section_count: 6,
    has_pdf: true, highlights: "exact",
  };
}

const PAPERS = [
  paper("bert", "BERT: Pre-training", "1810.04805"),
  paper("rag", "Retrieval-Augmented Generation", "2005.11401"),
  paper("lora", "LoRA"),
  paper("lost", "Lost in the Middle"),
  paper("attn", "Attention Is All You Need"),
];

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function row(aspect: ComparisonRow["aspect"], overrides: Partial<ComparisonRow> = {}): ComparisonRow {
  return {
    aspect,
    state: "ok",
    reason: null,
    cells: [
      part(`${aspect}:bert`, { text: `BERT ${aspect} claim [1].`, passages: [1] }),
      part(`${aspect}:rag`, { text: `RAG ${aspect} claim [2].`, citations: { valid: [2], invalid: [], uncited_sentences: [] }, passages: [2] }),
    ],
    until: null,
    tokens: {},
    ...overrides,
  };
}

function comparison(overrides: Partial<Comparison> = {}): Comparison {
  const rows = overrides.rows ?? [row("method"), row("results")];
  return {
    paper_ids: ["bert", "rag"],
    papers: [
      { paper_id: "bert", title: "BERT: Pre-training", arxiv_id: "1810.04805", label: "P1" },
      { paper_id: "rag", title: "Retrieval-Augmented Generation", arxiv_id: "2005.11401", label: "P2" },
    ],
    aspects: rows.map((r) => r.aspect),
    rows,
    passages: PASSAGES,
    plan: { max_requests: rows.length, parts: rows.map((r) => r.aspect) },
    requests: { planned: rows.length, retries: 0 },
    model: "nvidia/x:free",
    prompt_version: 8,
    created_at: new Date().toISOString(),
    status: "current",
    stale_reason: null,
    verified_cells: rows.flatMap((r) => r.cells).filter((c) => c.state === "verified").length,
    total_cells: rows.length * 2,
    pending: null,
    ...overrides,
  };
}

function controlledStream() {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({ start: (c) => void (controller = c) });
  return {
    response: new Response(body, { headers: { "Content-Type": "text/event-stream" } }),
    send(event: string, data: unknown) {
      controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
    },
    close: () => controller.close(),
  };
}

function streamOf(events: [string, unknown][]): Response {
  const stream = controlledStream();
  for (const [event, data] of events) stream.send(event, data);
  stream.close();
  return stream.response;
}

function backend(options: { saved?: Comparison | null; posts?: (Response | (() => Response))[]; remaining?: number } = {}) {
  const posted: Record<string, unknown>[] = [];
  const looked: string[] = [];
  const responses = [...(options.posts ?? [])];
  const remaining = options.remaining ?? 41;
  vi.stubGlobal("fetch", vi.fn(async (input: unknown, init: RequestInit = {}) => {
    const url = new URL(String(input));
    const method = init.method ?? "GET";
    if (url.pathname === "/api/status") return json({ state: "ready", model: "nvidia/x:free", model_is_free: true, daily_limit: 50 });
    if (url.pathname === "/api/usage") return json({ used: 50 - remaining, limit: 50, remaining, resets_at: "2026-11-09T00:00:00Z", source: "local" });
    if (url.pathname === "/api/papers") return json({ papers: PAPERS });
    if (url.pathname === "/api/comparisons" && method === "GET") {
      looked.push(url.search);
      return options.saved ? json(options.saved) : json({ kind: "not_saved", plan: { max_requests: 5 } }, 404);
    }
    if (url.pathname === "/api/comparisons" && method === "POST") {
      posted.push(JSON.parse(String(init.body)));
      const next = responses.shift();
      if (!next) throw new Error("no stream left");
      return typeof next === "function" ? next() : next;
    }
    throw new Error(`Unexpected ${method} ${url.pathname}`);
  }));
  return { posted, looked };
}

function view() {
  return render(
    <StatusProvider>
      <UsageProvider>
        <CompareView />
      </UsageProvider>
    </StatusProvider>,
  );
}

async function pick(user: ReturnType<typeof userEvent.setup>, ...titles: string[]) {
  for (const title of titles) {
    await user.selectOptions(await screen.findByRole("combobox", { name: "Add paper" }), title);
  }
}

const startButton = () => screen.findByRole("button", { name: "Compare papers" });

describe("Choosing papers and aspects", () => {
  it("cannot start with one paper and says why", async () => {
    backend();
    const user = userEvent.setup();
    view();
    await pick(user, "LoRA");
    expect(await startButton()).toBeDisabled();
    expect(screen.getByText("Choose at least 2 papers.")).toBeInTheDocument();
  });

  it("cannot start with five papers and says why", async () => {
    backend();
    const user = userEvent.setup();
    view();
    await pick(user, "BERT: Pre-training", "Retrieval-Augmented Generation", "LoRA", "Lost in the Middle", "Attention Is All You Need");
    expect(await startButton()).toBeDisabled();
    expect(screen.getByText("Choose at most 4 papers.")).toBeInTheDocument();
  });

  it("selects all five aspects by default, and cannot start with none", async () => {
    backend();
    const user = userEvent.setup();
    view();
    await pick(user, "BERT: Pre-training", "LoRA");
    const boxes = await screen.findAllByRole("checkbox");
    expect(boxes.map((b) => b.getAttribute("aria-label") ?? "")).toEqual(["Problem", "Method", "Datasets", "Results", "Limitations"]);
    for (const box of boxes) {
      expect(box).toBeChecked();
      await user.click(box);
    }
    expect(await startButton()).toBeDisabled();
    expect(screen.getByText("Choose at least 1 aspect.")).toBeInTheDocument();
  });

  it("removes a chosen paper with its chip", async () => {
    backend();
    const user = userEvent.setup();
    view();
    await pick(user, "LoRA");
    await user.click(await screen.findByRole("button", { name: "Remove LoRA" }));
    expect(screen.queryByRole("button", { name: "Remove LoRA" })).toBeNull();
  });

  it("shows the cost per aspect and today's remaining requests", async () => {
    backend();
    const user = userEvent.setup();
    view();
    await pick(user, "BERT: Pre-training", "LoRA");
    await user.click(await screen.findByRole("checkbox", { name: "Problem" }));
    expect(await screen.findByText("uses 4 requests, 1 per aspect · 41 left today")).toBeInTheDocument();
  });
});

describe("A running comparison", () => {
  it("shows progress per aspect, and a cell only from its part event", async () => {
    const stream = controlledStream();
    const { posted } = backend({ posts: [stream.response] });
    const user = userEvent.setup();
    view();
    await pick(user, "BERT: Pre-training", "Retrieval-Augmented Generation");
    for (const name of ["Problem", "Datasets", "Limitations"]) await user.click(await screen.findByRole("checkbox", { name }));
    await user.click(await startButton());
    await waitFor(() => expect(posted).toEqual([{ paper_ids: ["bert", "rag"], aspects: ["method", "results"] }]));

    stream.send("plan", { max_requests: 2, parts: ["method", "results"] });
    stream.send("progress", { part: "method", step: "generating" });
    expect(await screen.findByText("Writing method")).toBeInTheDocument();
    expect(screen.queryByText(/BERT method claim/)).toBeNull();
    stream.send("part", part("method:bert", { text: "BERT method claim [1].", passages: [1] }));
    expect(await screen.findByText(/BERT method claim/)).toBeInTheDocument();
    stream.send("comparison", comparison());
    stream.close();
    expect(await screen.findByText(/2 of 2 rows|4 of 4 cells verified/)).toBeInTheDocument();
  });
});

describe("A finished comparison", () => {
  async function opened(saved: Comparison) {
    const backendInfo = backend({ saved });
    const user = userEvent.setup();
    view();
    await pick(user, "BERT: Pre-training", "Retrieval-Augmented Generation");
    await screen.findByRole("table");
    return { user, ...backendInfo };
  }

  it("is a table with a column per paper and a row per aspect, with arXiv IDs", async () => {
    await opened(comparison());
    const table = screen.getByRole("table");
    expect(within(table).getByRole("columnheader", { name: /BERT: Pre-training.*1810\.04805/ })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: /Retrieval-Augmented Generation.*2005\.11401/ })).toBeInTheDocument();
    expect(within(table).getByRole("rowheader", { name: "Method" })).toBeInTheDocument();
    expect(within(table).getByRole("rowheader", { name: "Results" })).toBeInTheDocument();
    expect(within(table).getByText(/RAG results claim/)).toBeInTheDocument();
  });

  it("opens a cell's citation in the source viewer", async () => {
    const { user } = await opened(comparison());
    vi.mocked(fetch);
    await user.click(screen.getAllByRole("button", { name: /^Citation 2:/ })[0]!);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("shows a malformed row with its own retry", async () => {
    const saved = comparison({ rows: [row("method", { state: "failed", reason: "malformed", cells: [] }), row("results")], verified_cells: 2, total_cells: 4 });
    const posted = backend({ saved, posts: [streamOf([["comparison", comparison()]])] }).posted;
    const user = userEvent.setup();
    view();
    await pick(user, "BERT: Pre-training", "Retrieval-Augmented Generation");
    expect(await screen.findByText("This row couldn't be read")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry this row" }));
    await waitFor(() => expect(posted[0]).toMatchObject({ retry_aspects: ["method"], paper_ids: ["bert", "rag"], aspects: ["method", "results"] }));
  });

  it("shows held-back and not-reported cells beside verified ones", async () => {
    const saved = comparison({
      rows: [row("method", { cells: [
        part("method:bert", { state: "held_back", text: null, rejected_text: "Claim [9].", citations: { valid: [], invalid: [9], uncited_sentences: [] }, passages: [1] }),
        part("method:rag", { state: "not_reported", text: null, reason: "missing_cell", passages: [] }),
      ] })],
      verified_cells: 0,
      total_cells: 2,
    });
    await opened(saved);
    expect(screen.getByText(/Held back: this cell cited passage 9/)).toBeInTheDocument();
    expect(screen.getByText("Not reported in the retrieved passages.")).toBeInTheDocument();
  });

  it("states how many cells were verified and how passages were retrieved", async () => {
    await opened(comparison({ verified_cells: 8, total_cells: 10 }));
    expect(screen.getByText(/8 of 10 cells verified/)).toBeInTheDocument();
    expect(screen.getByText(/Passages were retrieved from each paper separately/)).toBeInTheDocument();
  });

  it("opens a saved comparison with no POST", async () => {
    const { posted, looked } = await opened(comparison());
    expect(posted).toEqual([]);
    expect(looked.at(-1)).toContain("papers=bert%2Crag");
  });

  it("regenerates only after showing the cost", async () => {
    const posted = backend({ saved: comparison(), posts: [streamOf([["comparison", comparison()]])] }).posted;
    const user = userEvent.setup();
    view();
    await pick(user, "BERT: Pre-training", "Retrieval-Augmented Generation");
    await user.click(await screen.findByRole("button", { name: "Regenerate comparison" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/It uses 5 requests/)).toBeInTheDocument();
    expect(posted).toEqual([]);
    await user.click(within(dialog).getByRole("button", { name: "Regenerate" }));
    await waitFor(() => expect(posted[0]).toMatchObject({ regenerate: true }));
  });

  it("marks an earlier comparison and offers no row retry", async () => {
    const saved = comparison({
      status: "stale",
      stale_reason: "passages_changed",
      rows: [row("method", { state: "failed", reason: "malformed", cells: [] })],
    });
    backend({ saved });
    const user = userEvent.setup();
    view();
    await pick(user, "BERT: Pre-training", "Retrieval-Augmented Generation");
    expect(await screen.findByText(/before one of these papers was re-processed/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry this row" })).toBeNull();
    expect(screen.getByRole("button", { name: "Regenerate comparison" })).toBeInTheDocument();
  });

  it("offers to finish a regeneration that did not finish, keeping the complete table", async () => {
    const pending = { created_at: new Date().toISOString(), failed_aspects: ["results"], retry_aspects: ["results"], verified_cells: 2 };
    const posted = backend({ saved: comparison({ pending }), posts: [streamOf([["comparison", comparison()]])] }).posted;
    const user = userEvent.setup();
    view();
    await pick(user, "BERT: Pre-training", "Retrieval-Augmented Generation");
    expect(await screen.findByText(/last regeneration did not finish Results/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Finish the regeneration" }));
    await waitFor(() => expect(posted[0]).toMatchObject({ retry_aspects: ["results"] }));
  });
});
