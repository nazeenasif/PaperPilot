import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { StatusProvider } from "@/components/app/StatusGate";
import { UsageProvider } from "@/components/app/UsageMeter";
import { CompareView } from "@/components/compare/CompareView";
import { PartState } from "@/components/summary/PartState";
import { SummaryView } from "@/components/summary/SummaryView";
import { partProblem } from "@/lib/errorKinds";
import type { Summary } from "@/lib/types";

import { part, summary } from "./summary-fixtures";

vi.mock("react-pdf", () => ({ Document: () => null, Page: () => null, pdfjs: { GlobalWorkerOptions: {} } }));

const encoder = new TextEncoder();
const RESETS = "2026-11-09T00:00:00Z";
const CARD = { page_count: 9, passage_count: 40, text_passages: 35, table_passages: 5, section_count: 6, has_pdf: true, highlights: "exact" };

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
    close: () => controller.close(),
  };
}

function backend(options: { remaining?: number; saved?: Summary | null; post?: () => Response }) {
  const posted: unknown[] = [];
  const calls = { usage: 0 };
  const remaining = options.remaining ?? 41;
  vi.stubGlobal("fetch", vi.fn(async (input: unknown, init: RequestInit = {}) => {
    const url = new URL(String(input));
    const method = init.method ?? "GET";
    if (url.pathname === "/api/status") return json({ state: "ready", model: "nvidia/x:free", model_is_free: true, daily_limit: 50 });
    if (url.pathname === "/api/usage") {
      calls.usage += 1;
      return json({ used: 50 - remaining, limit: 50, remaining, resets_at: RESETS, source: "local" });
    }
    if (url.pathname === "/api/summaries") return json({ papers: [], plan: { max_requests: 6 } });
    if (url.pathname === "/api/papers") {
      return json({ papers: [{ ...CARD, paper_id: "bert", title: "BERT", arxiv_id: null }, { ...CARD, paper_id: "rag", title: "RAG", arxiv_id: null }] });
    }
    if (url.pathname === "/api/summaries/lora" && method === "GET") {
      return options.saved ? json(options.saved) : json({ kind: "not_saved", plan: { max_requests: 6 } }, 404);
    }
    if (url.pathname === "/api/comparisons" && method === "GET") return json({ kind: "not_saved", plan: { max_requests: 5 } }, 404);
    if (method === "POST" && options.post) {
      posted.push(JSON.parse(String(init.body)));
      return options.post();
    }
    throw new Error(`Unexpected ${method} ${url.pathname}`);
  }));
  return { posted, calls };
}

function inProviders(node: React.ReactNode) {
  return render(
    <StatusProvider>
      <UsageProvider>{node}</UsageProvider>
    </StatusProvider>,
  );
}

describe("Too few requests left", () => {
  it("disables Summarize, shows the daily-limit state and says when requests resume", async () => {
    backend({ remaining: 5 });
    inProviders(<SummaryView paperId="lora" />);
    const button = await screen.findByRole("button", { name: "Summarize this paper" });
    await waitFor(() => expect(button).toBeDisabled());
    expect(screen.getByText("Daily limit")).toBeInTheDocument();
    expect(screen.getByText(/Summaries resume at/)).toBeInTheDocument();
    expect(screen.getByText(/uses 6 requests · 5 left today/)).toBeInTheDocument();
  });

  it("allows Summarize with exactly enough requests", async () => {
    backend({ remaining: 6 });
    inProviders(<SummaryView paperId="lora" />);
    await screen.findByText(/uses 6 requests · 6 left today/);
    expect(screen.getByRole("button", { name: "Summarize this paper" })).toBeEnabled();
  });

  it("still opens a saved summary, with Regenerate disabled", async () => {
    backend({ remaining: 0, saved: summary() });
    inProviders(<SummaryView paperId="lora" />);
    expect(await screen.findByText(/The problem of LoRA is stated here/)).toBeInTheDocument();
    await screen.findByText(/uses 6 requests · 0 left today/);
    expect(screen.getByRole("button", { name: "Regenerate summary" })).toBeDisabled();
  });

  it("disables Compare the same way", async () => {
    backend({ remaining: 2 });
    const user = userEvent.setup();
    inProviders(<CompareView />);
    await user.selectOptions(await screen.findByRole("combobox", { name: "Add paper" }), "BERT");
    await user.selectOptions(await screen.findByRole("combobox", { name: "Add paper" }), "RAG");
    await screen.findByText(/uses 5 requests, 1 per aspect · 2 left today/);
    expect(screen.getByRole("button", { name: "Compare papers" })).toBeDisabled();
    expect(screen.getByText(/Comparisons resume at/)).toBeInTheDocument();
  });

  it("lets fewer aspects fit the requests left", async () => {
    backend({ remaining: 2 });
    const user = userEvent.setup();
    inProviders(<CompareView />);
    await user.selectOptions(await screen.findByRole("combobox", { name: "Add paper" }), "BERT");
    await user.selectOptions(await screen.findByRole("combobox", { name: "Add paper" }), "RAG");
    for (const name of ["Problem", "Datasets", "Limitations"]) await user.click(screen.getByRole("checkbox", { name }));
    await screen.findByText(/uses 2 requests, 1 per aspect · 2 left today/);
    await waitFor(() => expect(screen.getByRole("button", { name: "Compare papers" })).toBeEnabled());
  });

  it("disables a part's retry when no request is left", async () => {
    backend({ remaining: 0, saved: summary({
      verified_parts: 5,
      sections: [part("problem"), part("method", { state: "failed", text: null, reason: "cut_off" }), part("data"), part("results"), part("limitations")],
    }) });
    inProviders(<SummaryView paperId="lora" />);
    const retry = await screen.findByRole("button", { name: "Retry this section" });
    await waitFor(() => expect(retry).toBeDisabled());
  });
});

describe("Refused or stopped runs", () => {
  it("shows a daily_limit refused before the stream as the daily-limit state, not a generic error", async () => {
    backend({ post: () => json({ kind: "daily_limit", needed: 6, used: 46, limit: 50, resets_at: RESETS }, 429) });
    const user = userEvent.setup();
    inProviders(<SummaryView paperId="lora" />);
    await user.click(await screen.findByRole("button", { name: "Summarize this paper" }));
    expect(await screen.findByText("Daily limit")).toBeInTheDocument();
    expect(screen.getByText("46 / 50")).toBeInTheDocument();
    expect(screen.queryByText(/couldn't finish/i)).toBeNull();
  });

  it("shows busy_task with the busy copy", async () => {
    backend({ post: () => json({ kind: "busy_task" }, 409) });
    const user = userEvent.setup();
    inProviders(<SummaryView paperId="lora" />);
    await user.click(await screen.findByRole("button", { name: "Summarize this paper" }));
    expect(await screen.findByText(/still working on another answer, summary or comparison/i)).toBeInTheDocument();
  });

  it("shows busy_task on Compare too", async () => {
    backend({ post: () => json({ kind: "busy_task" }, 409) });
    const user = userEvent.setup();
    inProviders(<CompareView />);
    await user.selectOptions(await screen.findByRole("combobox", { name: "Add paper" }), "BERT");
    await user.selectOptions(await screen.findByRole("combobox", { name: "Add paper" }), "RAG");
    await user.click(await screen.findByRole("button", { name: "Compare papers" }));
    expect(await screen.findByText(/still working on another answer, summary or comparison/i)).toBeInTheDocument();
  });

  it("says when requests resume on a part stopped by the daily limit", () => {
    render(<PartState noun="section" part={part("data", { state: "not_started", text: null, reason: "daily_limit", until: RESETS })} />);
    expect(screen.getByText(/today's free requests ran out\. They resume at \d\d:\d\d/)).toBeInTheDocument();
  });

  it("says when to try again on a part stopped by a long wait", () => {
    render(<PartState noun="section" part={part("data", { state: "not_started", text: null, reason: "rate_limited", until: RESETS })} />);
    expect(screen.getByText(/asked PaperPilot to wait\. Try again at \d\d:\d\d/)).toBeInTheDocument();
  });

  it.each([
    ["busy", "Not started: the free model was busy."],
    ["timeout", "Not started: the free model was busy."],
    ["unreachable", "Not started: the free model couldn't be reached."],
    ["bad_key", "Not started: the configured model couldn't be used."],
    ["out_of_credits", "Not started: the configured model couldn't be used."],
  ])("explains the engine's reason %s", (reason, copy) => {
    expect(partProblem("not_started", reason)).toBe(copy);
  });
});

describe("While a part waits", () => {
  it("shows the countdown with its attempt inside that part's card", async () => {
    const stream = controlledStream();
    backend({ post: () => stream.response });
    const user = userEvent.setup();
    inProviders(<SummaryView paperId="lora" />);
    await user.click(await screen.findByRole("button", { name: "Summarize this paper" }));
    stream.send("retry_wait", { part: "method", attempt: 1, max_attempts: 4, wait_seconds: 20, reason: "rate_limited" });
    const card = await screen.findByRole("region", { name: "Method" });
    expect(await within(card).findByText("attempt 2 of 4")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Data" })).queryByText(/attempt/)).toBeNull();
    stream.send("part", part("method"));
    await waitFor(() => expect(within(card).queryByText("attempt 2 of 4")).toBeNull());
    stream.close();
  });
});

describe("The usage meter", () => {
  it("is read again after a run", async () => {
    const stream = controlledStream();
    const { calls } = backend({ post: () => stream.response });
    const user = userEvent.setup();
    inProviders(<SummaryView paperId="lora" />);
    await user.click(await screen.findByRole("button", { name: "Summarize this paper" }));
    const before = calls.usage;
    stream.send("summary", summary());
    stream.close();
    await waitFor(() => expect(calls.usage).toBeGreaterThan(before));
  });
});
