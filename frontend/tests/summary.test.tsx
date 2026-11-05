import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { StatusProvider } from "@/components/app/StatusGate";
import { UsageProvider } from "@/components/app/UsageMeter";
import { PaperCard } from "@/components/library/PaperCard";
import { SectionCard } from "@/components/summary/SectionCard";
import { SummaryView } from "@/components/summary/SummaryView";
import type { Summary } from "@/lib/types";

import { PASSAGES, part, summary } from "./summary-fixtures";

vi.mock("react-pdf", () => ({ Document: () => null, Page: () => null, pdfjs: { GlobalWorkerOptions: {} } }));

const encoder = new TextEncoder();
const FACETS = ["problem", "method", "data", "results", "limitations"] as const;
const PAPER = "lora";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function controlledStream() {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({ start: (c) => void (controller = c) });
  return {
    response: new Response(body, { headers: { "Content-Type": "text/event-stream" } }),
    send(event: string, data: unknown) {
      controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
    },
    close() {
      controller.close();
    },
  };
}

/** fetch for status, usage, the saved summary (or 404 not_saved) and one POST stream. */
function backend(saved: Summary | null, stream?: ReturnType<typeof controlledStream>) {
  const posts: RequestInit[] = [];
  const fetchMock = vi.fn(async (input: unknown, init: RequestInit = {}) => {
    const path = new URL(String(input)).pathname;
    const method = init.method ?? "GET";
    if (path === "/api/status") return json({ state: "ready", model: "nvidia/x:free", model_is_free: true, daily_limit: 50 });
    if (path === "/api/usage") return json({ used: 9, limit: 50, remaining: 41, resets_at: "2026-10-26T00:00:00Z", source: "provider" });
    if (path === `/api/summaries/${PAPER}` && method === "GET") {
      return saved ? json({ ...saved, plan: { max_requests: 6 } }) : json({ kind: "not_saved", plan: { max_requests: 6 } }, 404);
    }
    if (path === `/api/summaries/${PAPER}` && method === "POST") {
      posts.push(init);
      if (!stream) throw new Error("no stream");
      return stream.response;
    }
    if (path.startsWith("/api/passages/")) {
      return json({ ...PASSAGES[0], page_count: 26, kind: "text", has_pdf: false, layout: null, layout_reason: "no_pdf", can_reprocess: false });
    }
    throw new Error(`Unexpected ${method} ${path}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return posts;
}

function renderView() {
  return render(
    <StatusProvider>
      <UsageProvider>
        <SummaryView paperId={PAPER} />
      </UsageProvider>
    </StatusProvider>,
  );
}

describe("Starting a summary", () => {
  it("shows the cost and today's remaining requests, and posts nothing until confirmed", async () => {
    const stream = controlledStream();
    const posts = backend(null, stream);
    const user = userEvent.setup();
    renderView();
    expect(await screen.findByText("uses 6 requests · 41 left today")).toBeInTheDocument();
    expect(posts).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Summarize this paper" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect((posts[0]?.headers as Record<string, string>)["X-PaperPilot"]).toBe("1");
  });
});

describe("Progress and parts", () => {
  it("shows progress per part, and a part's text only when its part event arrives", async () => {
    const stream = controlledStream();
    backend(null, stream);
    const user = userEvent.setup();
    renderView();
    await user.click(await screen.findByRole("button", { name: "Summarize this paper" }));
    stream.send("plan", { max_requests: 6, parts: [...FACETS, "tldr"] });
    stream.send("progress", { part: "method", step: "reading", passages: 4 });
    expect(await screen.findByText("Reading method passages")).toBeInTheDocument();
    stream.send("progress", { part: "method", step: "generating" });
    expect(await screen.findByText("Writing method")).toBeInTheDocument();
    stream.send("progress", { part: "method", step: "checking" });
    expect(await screen.findByText("Checking method")).toBeInTheDocument();
    expect(screen.queryByText(/The method of LoRA/)).not.toBeInTheDocument();
    stream.send("part", part("method"));
    expect(await screen.findByText(/The method of LoRA is stated here/)).toBeInTheDocument();
    stream.send("summary", summary());
    stream.close();
    expect(await screen.findByText(/LoRA freezes the model/)).toBeInTheDocument();
  });

  it("shows the TL;DR card and five sections in order, each with its passages read", async () => {
    backend(summary());
    renderView();
    const tldr = await screen.findByRole("region", { name: "TL;DR" });
    expect(within(tldr).getByText(/Built only from the verified sections below/)).toBeInTheDocument();
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(["Problem", "Method", "Data", "Results", "Limitations"]);
    expect(screen.getAllByText("4 passages read")).toHaveLength(5);
  });

  it("opens a citation in the source viewer", async () => {
    backend(summary());
    const user = userEvent.setup();
    renderView();
    const method = await screen.findByRole("region", { name: "Method" });
    await user.click(within(method).getByRole("button", { name: /^Citation 1:/ }));
    expect(await screen.findByRole("dialog")).toHaveTextContent("LoRA: Low-Rank Adaptation of Large Language Models");
  });

  it("claims All citations verified only when every part is verified", async () => {
    backend(summary());
    const { unmount } = renderView();
    expect(await screen.findByText("All citations verified")).toBeInTheDocument();
    unmount();
    backend(summary({ verified_parts: 5, sections: [part("problem"), part("method", { state: "not_reported", text: null, reason: "no_citations" }), ...FACETS.slice(2).map((f) => part(f))] }));
    renderView();
    await screen.findByRole("region", { name: "TL;DR" });
    expect(screen.queryByText("All citations verified")).not.toBeInTheDocument();
    expect(screen.getByText("5 of 6 parts verified")).toBeInTheDocument();
  });
});

describe("Uncited sentences", () => {
  const cited = "The second sentence is cited [1].";
  const uncited = "The first sentence has no citation.";
  const render_ = (overrides: Parameters<typeof part>[1]) =>
    render(
      <SectionCard
        label="Limitations"
        part={part("limitations", overrides)}
        progress={undefined}
        passages={new Map(PASSAGES.map((p) => [p.number, p]))}
        onOpen={() => {}}
      />,
    );

  it("marks an uncited sentence and counts it, as Ask does", () => {
    const { container } = render_({
      text: `${uncited} ${cited}`,
      citations: { valid: [1], invalid: [], uncited_sentences: [uncited] },
    });
    const flagged = container.querySelectorAll("[data-uncited]");
    expect(flagged).toHaveLength(1);
    expect(flagged[0].textContent).toContain(uncited);
    expect(flagged[0].getAttribute("title")).toBe("This sentence has no citation");
    expect(screen.getByText("1 sentence has no citation")).toBeInTheDocument();
  });

  it("marks nothing when every sentence is cited", () => {
    const { container } = render_({ text: cited });
    expect(container.querySelectorAll("[data-uncited]")).toHaveLength(0);
    expect(screen.queryByText(/no citation/)).toBeNull();
  });
});

describe("From the Library", () => {
  it("the paper card's Summarize button opens that paper's summary", () => {
    render(
      <PaperCard
        paper={{ paper_id: PAPER, title: "LoRA", page_count: 26, passage_count: 56, text_passages: 44, table_passages: 12,
          section_count: 10, arxiv_id: "2106.09685", has_pdf: true, highlights: "exact" }}
        onDeleted={() => undefined}
      />,
    );
    expect(screen.getByRole("link", { name: "Summarize" })).toHaveAttribute("href", `/summarize/${PAPER}`);
  });
});
