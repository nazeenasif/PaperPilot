import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Header, modelLabel } from "@/components/app/Header";
import { StatusGate, StatusProvider } from "@/components/app/StatusGate";
import type { Status } from "@/lib/types";

const READY: Status = {
  state: "ready",
  model: "nvidia/nemotron-3-ultra-550b-a55b:free",
  model_is_free: true,
  daily_limit: 50,
};

function statusResponse(status: Partial<Status>): Response {
  return new Response(JSON.stringify({ ...READY, ...status }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function renderShell() {
  return render(
    <StatusProvider>
      <Header />
      <StatusGate>
        <p>Ask screen</p>
      </StatusGate>
    </StatusProvider>,
  );
}

/** Let pending promises (fetch, json) settle, then advance fake time. */
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("StatusGate", () => {
  it("shows Getting ready while the model loads, and hides the app", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(statusResponse({ state: "loading" })));
    renderShell();
    await advance(0);
    expect(screen.getByRole("status")).toHaveTextContent(/getting ready/i);
    expect(screen.queryByText("Ask screen")).not.toBeInTheDocument();
  });

  it("shows the app once the server is ready", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(statusResponse({})));
    renderShell();
    await advance(0);
    expect(screen.getByText("Ask screen")).toBeInTheDocument();
  });

  it("explains how to start the server when it cannot be reached, then recovers", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValue(statusResponse({}));
    vi.stubGlobal("fetch", fetchMock);
    renderShell();
    await advance(0);
    expect(screen.getByRole("alert")).toHaveTextContent(/can.t reach paperpilot/i);
    expect(screen.getByText("python -m api")).toBeInTheDocument();
    expect(screen.queryByText("Ask screen")).not.toBeInTheDocument();

    await advance(2000);
    expect(screen.getByText("Ask screen")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a designed message, with no internals, when the server failed to load", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(statusResponse({ state: "error" })));
    renderShell();
    await advance(0);
    expect(screen.getByRole("alert")).toHaveTextContent(/couldn.t start/i);
    expect(screen.getByRole("alert")).toHaveTextContent(/api\.log/);
  });

  it("polls every 2 s until ready, then every 30 s", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(statusResponse({ state: "loading" }))
      .mockResolvedValue(statusResponse({}));
    vi.stubGlobal("fetch", fetchMock);
    renderShell();
    await advance(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await advance(2000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getByText("Ask screen")).toBeInTheDocument();
    await advance(29_000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    await advance(1000);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});

describe("Header", () => {
  it("shows the name and a model chip marked free", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(statusResponse({})));
    renderShell();
    await advance(0);
    expect(screen.getByRole("banner")).toHaveTextContent("PaperPilot");
    expect(screen.getByText("nemotron-3-ultra · free")).toBeInTheDocument();
  });

  it("labels models readably", () => {
    expect(modelLabel("nvidia/nemotron-3-ultra-550b-a55b:free", true)).toBe("nemotron-3-ultra · free");
    expect(modelLabel("google/gemma-4-31b-it:free", true)).toBe("gemma-4-31b-it · free");
    expect(modelLabel("openai/gpt-5-mini", false)).toBe("gpt-5-mini");
  });
});
