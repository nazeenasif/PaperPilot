import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { StatusProvider } from "@/components/app/StatusGate";
import { UsageProvider } from "@/components/app/UsageMeter";
import { SummaryView } from "@/components/summary/SummaryView";
import type { Summary } from "@/lib/types";

import { part, summary } from "./summary-fixtures";

vi.mock("react-pdf", () => ({ Document: () => null, Page: () => null, pdfjs: { GlobalWorkerOptions: {} } }));

const encoder = new TextEncoder();

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** The first POST streams `events` and stays open, so the view can be seen mid-run. */
function backend(saved: Summary, events: [string, unknown][] = [], close = true) {
  const posted: unknown[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: unknown, init: RequestInit = {}) => {
    const path = new URL(String(input)).pathname;
    if (path === "/api/status") return json({ state: "ready", model: "m:free", model_is_free: true, daily_limit: 50 });
    if (path === "/api/usage") return json({ used: 9, limit: 50, remaining: 41, resets_at: "2026-11-05T00:00:00Z", source: "provider" });
    if (path === "/api/summaries") return json({ papers: [], plan: { max_requests: 6 } });
    if (init.method === "POST") {
      posted.push(JSON.parse(String(init.body)));
      const text = events.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join("");
      return new Response(new ReadableStream({ start: (c) => { c.enqueue(encoder.encode(text)); if (close) c.close(); } }),
        { headers: { "Content-Type": "text/event-stream" } });
    }
    return json(saved);
  }));
  return posted;
}

function renderView() {
  return render(<StatusProvider><UsageProvider><SummaryView paperId="lora" /></UsageProvider></StatusProvider>);
}

const WITHOUT_METHOD = summary({
  tldr: part("tldr", { built_from: ["problem", "data", "results", "limitations"], built_without: ["method"] }),
});

describe("A TL;DR built without a section", () => {
  it("says so, offers to rewrite it for 1 request, and does not claim All citations verified", async () => {
    const posted = backend(WITHOUT_METHOD, [["summary", summary()]]);
    const user = userEvent.setup();
    renderView();
    const tldr = await screen.findByRole("region", { name: "TL;DR" });
    expect(within(tldr).getByText("Built without Method.")).toBeInTheDocument();
    expect(await within(tldr).findByText("uses 1 request · 41 left today")).toBeInTheDocument();
    expect(screen.queryByText("All citations verified")).not.toBeInTheDocument();
    await user.click(within(tldr).getByRole("button", { name: "Rewrite the TL;DR" }));
    await waitFor(() => expect(posted).toEqual([{ retry_parts: ["tldr"] }]));
    expect(await screen.findByText("All citations verified")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "TL;DR" })).queryByText(/Built without/)).not.toBeInTheDocument();
  });

  it("names several sections", async () => {
    backend(summary({ tldr: part("tldr", { built_without: ["method", "data"] }) }));
    renderView();
    expect(await screen.findByText("Built without Method and Data.")).toBeInTheDocument();
  });

  it("shows nothing extra when the TL;DR used every section", async () => {
    backend(summary());
    renderView();
    await screen.findByText("All citations verified");
    expect(screen.queryByText(/Built without/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Rewrite the TL;DR" })).not.toBeInTheDocument();
  });
});

describe("While one part is retried", () => {
  it("keeps the other saved parts on screen", async () => {
    const failed = summary({
      verified_parts: 5,
      sections: [part("problem"), part("method", { state: "failed", text: null, reason: "cut_off" }),
        part("data"), part("results"), part("limitations")],
    });
    backend(failed, [["plan", { max_requests: 1, parts: ["method"] }], ["progress", { part: "method", step: "generating" }]], false);
    const user = userEvent.setup();
    renderView();
    const method = await screen.findByRole("region", { name: "Method" });
    await user.click(within(method).getByRole("button", { name: "Retry this section" }));
    expect(await screen.findByText("Writing method")).toBeInTheDocument();
    expect(screen.getByText(/The problem of LoRA is stated here/)).toBeInTheDocument();
    expect(screen.getByText(/The results of LoRA is stated here/)).toBeInTheDocument();
  });
});
