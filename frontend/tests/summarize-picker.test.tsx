import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { StatusProvider } from "@/components/app/StatusGate";
import { UsageProvider } from "@/components/app/UsageMeter";
import { SummarizePicker } from "@/components/summary/SummarizePicker";
import { SummaryView } from "@/components/summary/SummaryView";
import type { Summary, SummaryListItem } from "@/lib/types";

import { part, summary } from "./summary-fixtures";

vi.mock("react-pdf", () => ({ Document: () => null, Page: () => null, pdfjs: { GlobalWorkerOptions: {} } }));

const encoder = new TextEncoder();
const TWO_HOURS_AGO = () => new Date(Date.now() - 2 * 3600 * 1000).toISOString();

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function streamOf(events: [string, unknown][]): Response {
  const text = events.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join("");
  return new Response(new ReadableStream({ start: (c) => (c.enqueue(encoder.encode(text)), c.close()) }), {
    headers: { "Content-Type": "text/event-stream" },
  });
}

/** fetch for status, usage, the summaries list, one saved summary and POST streams. */
function backend(options: { list?: SummaryListItem[]; saved?: Summary | null; posts?: [string, unknown][][] }) {
  const posted: Record<string, unknown>[] = [];
  const streams = [...(options.posts ?? [])];
  vi.stubGlobal("fetch", vi.fn(async (input: unknown, init: RequestInit = {}) => {
    const path = new URL(String(input)).pathname;
    const method = init.method ?? "GET";
    if (path === "/api/status") return json({ state: "ready", model: "nvidia/x:free", model_is_free: true, daily_limit: 50 });
    if (path === "/api/usage") return json({ used: 9, limit: 50, remaining: 41, resets_at: "2026-10-26T00:00:00Z", source: "provider" });
    if (path === "/api/summaries") return json({ papers: options.list ?? [], plan: { max_requests: 6 } });
    if (path === "/api/summaries/lora" && method === "GET") {
      return options.saved ? json(options.saved) : json({ kind: "not_saved", plan: { max_requests: 6 } }, 404);
    }
    if (path === "/api/summaries/lora" && method === "POST") {
      posted.push(JSON.parse(String(init.body)));
      const next = streams.shift();
      if (!next) throw new Error("no stream left");
      return streamOf(next);
    }
    throw new Error(`Unexpected ${method} ${path}`);
  }));
  return posted;
}

function inProviders(node: React.ReactNode) {
  return render(
    <StatusProvider>
      <UsageProvider>{node}</UsageProvider>
    </StatusProvider>,
  );
}

const LIST: SummaryListItem[] = [
  { paper_id: "att", title: "Attention Is All You Need", arxiv_id: "1706.03762", summary: { status: "none", created_at: null, model: null } },
  { paper_id: "lora", title: "LoRA: Low-Rank Adaptation", arxiv_id: "2106.09685", summary: { status: "current", created_at: "2026-10-25T10:00:00+00:00", model: "nvidia/x:free" } },
  { paper_id: "rag", title: "Retrieval-Augmented Generation", arxiv_id: null, summary: { status: "stale", created_at: "2026-10-20T10:00:00+00:00", model: "old/model:free" } },
];

describe("The Summarize tab", () => {
  it("lists every paper with its summary status and links to it", async () => {
    backend({ list: LIST });
    inProviders(<SummarizePicker />);
    const items = await screen.findAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(within(items[0]!).getByText("Not summarized yet")).toBeInTheDocument();
    expect(within(items[1]!).getByText(/^Saved /)).toBeInTheDocument();
    expect(within(items[2]!).getByText("Generated with an earlier model")).toBeInTheDocument();
    expect(within(items[1]!).getByRole("link")).toHaveAttribute("href", "/summarize/lora");
  });
});

describe("A saved summary", () => {
  it("opens with its age and a reopening cost of 0 requests, posting nothing", async () => {
    const posted = backend({ saved: summary({ created_at: TWO_HOURS_AGO() }) });
    inProviders(<SummaryView paperId="lora" />);
    expect(await screen.findByText("Saved 2 hours ago · reopening cost 0 requests")).toBeInTheDocument();
    expect(screen.getByText("All citations verified")).toBeInTheDocument();
    expect(posted).toHaveLength(0);
  });

  it("labels a stale summary with its reason and never as current", async () => {
    backend({ saved: summary({ status: "stale", stale_reason: "model_changed" }) });
    inProviders(<SummaryView paperId="lora" />);
    expect(await screen.findByText(/Generated with an earlier model/)).toBeInTheDocument();
    expect(screen.queryByText("All citations verified")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Regenerate summary" })).toBeInTheDocument();
  });

  it("Regenerate shows the cost, asks for confirmation, then replaces the view", async () => {
    const replaced = summary({ tldr: part("tldr", { text: "A regenerated TL;DR sentence [1]." }) });
    const posted = backend({ saved: summary(), posts: [[["summary", replaced]]] });
    const user = userEvent.setup();
    inProviders(<SummaryView paperId="lora" />);
    await user.click(await screen.findByRole("button", { name: "Regenerate summary" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("uses 6 requests");
    expect(posted).toHaveLength(0);
    await user.click(within(dialog).getByRole("button", { name: "Regenerate" }));
    expect(await screen.findByText(/A regenerated TL;DR sentence/)).toBeInTheDocument();
    expect(posted).toEqual([{ regenerate: true }]);
  });

  it("keeps the saved summary when a regeneration fails", async () => {
    backend({ saved: summary(), posts: [[["error", { kind: "model_busy", attempts: 4 }]]] });
    const user = userEvent.setup();
    inProviders(<SummaryView paperId="lora" />);
    await user.click(await screen.findByRole("button", { name: "Regenerate summary" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Regenerate" }));
    expect(await screen.findByText("The free model is still busy")).toBeInTheDocument();
    expect(screen.getByText(/The problem of LoRA is stated here/)).toBeInTheDocument();
  });

  it("offers to retry a failed section with its cost", async () => {
    const failed = summary({
      verified_parts: 5,
      sections: [part("problem"), part("method", { state: "failed", text: null, reason: "cut_off" }),
        part("data"), part("results"), part("limitations")],
    });
    const posted = backend({ saved: failed, posts: [[["summary", summary()]]] });
    const user = userEvent.setup();
    inProviders(<SummaryView paperId="lora" />);
    const method = await screen.findByRole("region", { name: "Method" });
    const retry = within(method).getByRole("button", { name: "Retry this section" });
    expect(within(method).getByText("uses 2 requests · 41 left today")).toBeInTheDocument();
    await user.click(retry);
    await waitFor(() => expect(posted).toEqual([{ retry_parts: ["method"] }]));
  });
});
