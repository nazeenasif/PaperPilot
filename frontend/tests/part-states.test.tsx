import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { StatusProvider } from "@/components/app/StatusGate";
import { UsageProvider } from "@/components/app/UsageMeter";
import { PartState } from "@/components/summary/PartState";
import { SummaryView } from "@/components/summary/SummaryView";

import { part, summary } from "./summary-fixtures";

vi.mock("react-pdf", () => ({ Document: () => null, Page: () => null, pdfjs: { GlobalWorkerOptions: {} } }));

const ENGINE_WARNING = "The answer was rejected: it cited [14], but only passages [9]-[12] were provided.";

describe("PartState", () => {
  it("reads Not reported in the retrieved passages for an unsupported part", () => {
    render(<PartState part={part("method", { state: "not_reported", text: null, reason: "no_citations" })} noun="section" />);
    expect(screen.getByText("Not reported in the retrieved passages.")).toBeInTheDocument();
  });

  it("holds back a part in the app's own words and reveals the unverified text on request", async () => {
    const held = part("data", {
      state: "held_back", text: null, reason: "invalid_citations", warning: ENGINE_WARNING,
      rejected_text: "Experiments use GLUE and SQuAD [14].", passages: [9, 10, 11, 12],
      citations: { valid: [], invalid: [14], uncited_sentences: [] },
    });
    const user = userEvent.setup();
    render(<PartState part={held} noun="section" />);
    expect(screen.getByText("Held back: this section cited passage 14, but only passages 9–12 were provided.")).toBeInTheDocument();
    expect(screen.queryByText(ENGINE_WARNING)).not.toBeInTheDocument();
    expect(screen.queryByText(/GLUE and SQuAD/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "View the unverified text" }));
    expect(screen.getByText("Not verified")).toBeInTheDocument();
    expect(screen.getByText(/GLUE and SQuAD/)).toBeInTheDocument();
    expect(screen.getByLabelText("Citation 14: not among the provided passages")).toBeInTheDocument();
  });

  it("lists scattered provided passages by number", () => {
    const held = part("data", { state: "held_back", text: null, passages: [3, 7, 8],
      rejected_text: "x [2].", citations: { valid: [], invalid: [2], uncited_sentences: [] } });
    render(<PartState part={held} noun="cell" />);
    expect(screen.getByText("Held back: this cell cited passage 2, but only passages 3, 7 and 8 were provided.")).toBeInTheDocument();
  });

  it("shows a cut-off part as failed with a retry, never with truncated text", async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();
    render(<PartState part={part("results", { state: "failed", text: null, reason: "cut_off" })} noun="section" onRetry={onRetry} retryCost={2} />);
    expect(screen.getByText("The model's answer was cut off before it finished.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry this section" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["empty", "failed", "The model returned an empty answer."],
    ["daily_limit", "not_started", "Not started: today's free requests ran out."],
    ["rate_limited", "not_started", "Not started: the free model asked PaperPilot to wait."],
    ["model_busy", "not_started", "Not started: the free model was busy."],
  ] as const)("explains %s", (reason, state, copy) => {
    render(<PartState part={part("method", { state, text: null, reason })} noun="section" />);
    expect(screen.getByText(copy)).toBeInTheDocument();
  });

  it("explains a held-back TL;DR in plain words, without the engine's wording", () => {
    const tldr = part("tldr", { state: "held_back", text: null, reason: "tldr_check",
      warning: "sentence 1 states 20,000, which its sources do not contain",
      rejected_text: "It is 20,000 times smaller [4].", citations: { valid: [4], invalid: [], uncited_sentences: [] } });
    render(<PartState part={tldr} noun="TL;DR" />);
    expect(screen.getByText("Held back: the TL;DR said something its verified sections don't support.")).toBeInTheDocument();
    expect(screen.queryByText(/sources do not contain/)).not.toBeInTheDocument();
  });
});

describe("In a summary", () => {
  it("keeps every other section visible around a held-back TL;DR and a not-reported section", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: unknown) => {
      const path = new URL(String(input)).pathname;
      const body = path === "/api/summaries/lora"
        ? summary({
            verified_parts: 4,
            tldr: part("tldr", { state: "held_back", text: null, reason: "tldr_check", rejected_text: "Uncited.",
              citations: { valid: [], invalid: [], uncited_sentences: ["Uncited."] } }),
            sections: [part("problem"), part("method", { state: "not_reported", text: null, reason: "no_citations" }),
              part("data"), part("results"), part("limitations")],
          })
        : path === "/api/status" ? { state: "ready", model: "m:free", model_is_free: true, daily_limit: 50 }
        : path === "/api/usage" ? { used: 9, limit: 50, remaining: 41, resets_at: "2026-10-26T00:00:00Z", source: "provider" }
        : { papers: [], plan: { max_requests: 6 } };
      return new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
    }));
    render(<StatusProvider><UsageProvider><SummaryView paperId="lora" /></UsageProvider></StatusProvider>);
    const tldr = await screen.findByRole("region", { name: "TL;DR" });
    expect(within(tldr).getByText(/Held back: the TL;DR/)).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Method" })).getByText("Not reported in the retrieved passages.")).toBeInTheDocument();
    for (const name of ["Problem", "Data", "Results", "Limitations"]) {
      expect(within(screen.getByRole("region", { name })).getByText(/is stated here/)).toBeInTheDocument();
    }
  });
});
