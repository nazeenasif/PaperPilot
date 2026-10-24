import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Header } from "@/components/app/Header";
import { StatusProvider } from "@/components/app/StatusGate";
import { UsageMeter, UsageProvider } from "@/components/app/UsageMeter";
import { AskScreen } from "@/components/ask/AskScreen";
import type { Answer, Status, Usage } from "@/lib/types";

const STATUS: Status = { state: "ready", model: "nvidia/nemotron-3-ultra-550b-a55b:free", model_is_free: true, daily_limit: 50 };
const encoder = new TextEncoder();

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

function usage(used: number, limit = 50): Usage {
  return { used, limit, remaining: Math.max(limit - used, 0), resets_at: "2026-10-26T00:00:00Z", source: "provider" };
}

/** fetch for status, usage (one reading per call, the last repeating) and optional ask streams. */
function backend(readings: Usage[], askBody?: string) {
  const usageCalls: number[] = [];
  const fetchMock = vi.fn(async (input: unknown) => {
    const path = new URL(String(input)).pathname;
    if (path === "/api/status") return json(STATUS);
    if (path === "/api/usage") {
      usageCalls.push(1);
      return json(readings[Math.min(usageCalls.length - 1, readings.length - 1)]);
    }
    if (path === "/api/ask" && askBody !== undefined) {
      return new Response(new ReadableStream({ start: (c) => (c.enqueue(encoder.encode(askBody)), c.close()) }), {
        headers: { "Content-Type": "text/event-stream" },
      });
    }
    throw new Error(`Unexpected ${path}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return usageCalls;
}

function renderMeter(extra?: React.ReactNode) {
  return render(
    <StatusProvider>
      <UsageProvider>
        <UsageMeter />
        {extra}
      </UsageProvider>
    </StatusProvider>,
  );
}

afterEach(() => {
  vi.useRealTimers();
});

describe("UsageMeter", () => {
  it("shows today's requests against the limit", async () => {
    backend([usage(34)]);
    renderMeter();
    const meter = await screen.findByRole("status", { name: /requests today/i });
    expect(meter).toHaveTextContent("Requests today 34 / 50");
  });

  it("refreshes every 60 seconds", async () => {
    vi.useFakeTimers();
    const calls = backend([usage(34), usage(35)]);
    renderMeter();
    await act(async () => void (await vi.advanceTimersByTimeAsync(100)));
    expect(screen.getByRole("status", { name: /requests today/i })).toHaveTextContent("34 / 50");
    await act(async () => void (await vi.advanceTimersByTimeAsync(60_000)));
    expect(screen.getByRole("status", { name: /requests today/i })).toHaveTextContent("35 / 50");
    expect(calls.length).toBe(2);
  });

  it("takes the figure from each answer without asking the server again", async () => {
    const answer = { text: "LoRA adapts models [1].", not_found: false, rejected_answer: null, verified: true,
      citations: { valid: [1], invalid: [], uncited_sentences: [] }, passages: [], fallback_reason: null,
      timings: { rewrite: 0, retrieve: 0, generate: 1 }, usage: usage(36) } as unknown as Answer;
    const calls = backend([usage(34)], `event: answer\ndata: ${JSON.stringify(answer)}\n\n`);
    const user = userEvent.setup();
    renderMeter(<AskScreen />);
    await screen.findByText("34 / 50");
    await user.type(screen.getByRole("textbox", { name: /ask about your papers/i }), "What is LoRA?{Enter}");
    expect(await screen.findByText("36 / 50")).toBeInTheDocument();
    expect(calls.length).toBe(1);
  });

  it("turns amber when 5 or fewer requests remain", async () => {
    backend([usage(44)]);
    const { unmount } = renderMeter();
    expect(await screen.findByText("44 / 50")).not.toHaveClass("text-amber");
    unmount();
    backend([usage(45)]);
    renderMeter();
    expect(await screen.findByText("45 / 50")).toHaveClass("text-amber");
  });

  it("at the limit, links to the daily-limit state", async () => {
    backend([usage(50)]);
    const user = userEvent.setup();
    renderMeter();
    await user.click(await screen.findByRole("button", { name: /daily limit reached/i }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("free requests used today")).toBeInTheDocument();
    expect(within(dialog).getByText("50 / 50")).toBeInTheDocument();
  });

  it("sits in the header beside the model chip, which says free for :free models", async () => {
    backend([usage(34)]);
    render(
      <StatusProvider>
        <UsageProvider>
          <Header />
        </UsageProvider>
      </StatusProvider>,
    );
    expect(await screen.findByText("nemotron-3-ultra · free")).toBeInTheDocument();
    expect(await screen.findByRole("status", { name: /requests today/i })).toHaveTextContent("34 / 50");
  });
});
