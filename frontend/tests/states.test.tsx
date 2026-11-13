import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AskScreen } from "@/components/ask/AskScreen";
import { Busy } from "@/components/states/Busy";
import { DailyLimit } from "@/components/states/DailyLimit";
import { ModelUnavailable } from "@/components/states/ModelUnavailable";
import { NotFound } from "@/components/states/NotFound";
import { PassageGone } from "@/components/states/PassageGone";
import { UploadRow } from "@/components/library/UploadRow";
import type { Answer } from "@/lib/types";

const encoder = new TextEncoder();
const NOT_FOUND = "I couldn't find that in the selected papers.";

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

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const PASSAGES = Array.from({ length: 6 }, (_, i) => ({
  number: i + 1,
  passage_id: `lora-${i + 1}`,
  paper_id: "lora",
  title: "LoRA: Low-Rank Adaptation",
  section: "Our Method",
  page: 5,
  score: 0.7,
  text: "x",
}));

function answer(overrides: Partial<Answer> = {}): Answer {
  return {
    question: "What is LoRA?",
    standalone_question: "What is LoRA?",
    rewrite_applied: false,
    rewrite_fallback_reason: null,
    text: "LoRA adapts large models efficiently [1].",
    not_found: false,
    fallback_reason: null,
    warning: null,
    rejected_answer: null,
    citations: { valid: [1], invalid: [], uncited_sentences: [] },
    verified: true,
    passages: PASSAGES,
    papers_read: 1,
    word_count: 6,
    llm_calls: 1,
    requests: { planned: 1, retries: 0 },
    timings: { rewrite: 0, retrieve: 0.1, generate: 2 },
    tokens: {},
    usage: { used: 34, limit: 50, remaining: 16, resets_at: "2026-10-26T00:00:00Z", source: "provider" },
    ...overrides,
  };
}

/** The researcher's local HH:MM for an ISO time, as the states must show it. */
function local(iso: string): string {
  return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(iso));
}

/** Ask a question on the Ask screen; every POST /api/ask gets the next stream. */
async function askWith(...streams: ReturnType<typeof controlledStream>[]) {
  const queue = [...streams];
  const fetchMock = vi.fn(async (input: unknown, init: RequestInit = {}) => {
    const path = new URL(String(input)).pathname;
    if (path === "/api/ask") {
      const next = queue.shift();
      if (!next) throw new Error("no stream left");
      return next.response;
    }
    if (path === "/api/search") {
      return json({ results: [{ rank: 1, score: 0.7, passage_id: "lora-1", paper_id: "lora", title: "LoRA: Low-Rank Adaptation", section: "Our Method", page: 5, text: "LoRA freezes the pretrained weights." }] });
    }
    throw new Error(`Unexpected ${init.method ?? "GET"} ${path}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  const user = userEvent.setup();
  render(<AskScreen />);
  await user.type(screen.getByRole("textbox", { name: /ask about your papers/i }), "What is LoRA?{Enter}");
  return { user, fetchMock };
}

afterEach(() => {
  vi.useRealTimers();
});

describe("NotFound", () => {
  it("shows the exact sentence and suggestions; Search all papers only when some are left out", async () => {
    const onSearchAll = vi.fn();
    const onRephrase = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(<NotFound canSearchAll onSearchAll={onSearchAll} onRephrase={onRephrase} />);
    expect(screen.getByText(NOT_FOUND)).toBeInTheDocument();
    expect(screen.getByText(/only answers from your library/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Search all papers" }));
    expect(onSearchAll).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: "Rephrase more specifically" }));
    expect(onRephrase).toHaveBeenCalledTimes(1);
    rerender(<NotFound canSearchAll={false} onSearchAll={onSearchAll} onRephrase={onRephrase} />);
    expect(screen.queryByRole("button", { name: "Search all papers" })).not.toBeInTheDocument();
  });

  it("Rephrase more specifically focuses the composer", async () => {
    const stream = controlledStream();
    const { user } = await askWith(stream);
    stream.send("answer", answer({ text: NOT_FOUND, not_found: true, verified: false, fallback_reason: "below_threshold",
      passages: [], citations: { valid: [], invalid: [], uncited_sentences: [] } }));
    stream.close();
    await user.click(await screen.findByRole("button", { name: "Rephrase more specifically" }));
    expect(screen.getByRole("textbox", { name: /ask about your papers/i })).toHaveFocus();
  });
});

describe("Busy", () => {
  const RETRY = { attempt: 1, max_attempts: 4, wait_seconds: 8, reason: "rate_limited" as const };

  it("counts down live and keeps counting through re-renders", () => {
    vi.useFakeTimers();
    const since = Date.now();
    const { rerender } = render(<Busy retry={RETRY} since={since} />);
    expect(screen.getByText("0:08")).toBeInTheDocument();
    expect(screen.getByText("attempt 2 of 4")).toBeInTheDocument();
    expect(screen.getByText("The free model is busy right now")).toBeInTheDocument();
    expect(screen.getByText(/your question is safe/i)).toBeInTheDocument();
    act(() => void vi.advanceTimersByTime(3_000));
    expect(screen.getByText("0:05")).toBeInTheDocument();
    rerender(<Busy retry={{ ...RETRY }} since={since} />);
    expect(screen.getByText("0:05")).toBeInTheDocument();
    act(() => void vi.advanceTimersByTime(10_000));
    expect(screen.getByText("0:00")).toBeInTheDocument();
  });

  it("appears on the Ask screen for a retry_wait event, then gives way to the answer", async () => {
    const stream = controlledStream();
    await askWith(stream);
    stream.send("retry_wait", RETRY);
    expect(await screen.findByText("attempt 2 of 4")).toBeInTheDocument();
    stream.send("answer", answer());
    stream.close();
    expect(await screen.findByText(/adapts large models/)).toBeInTheDocument();
    expect(screen.queryByText("attempt 2 of 4")).not.toBeInTheDocument();
  });
});

describe("ModelBusy", () => {
  it("keeps the question and Try again asks it again", async () => {
    const first = controlledStream();
    const second = controlledStream();
    const { user, fetchMock } = await askWith(first, second);
    first.send("error", { kind: "model_busy", attempts: 4 });
    first.close();
    expect(await screen.findByText("The free model is still busy")).toBeInTheDocument();
    expect(screen.getByText(/tried 4 times/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    const asks = () => fetchMock.mock.calls.filter(([input]) => new URL(String(input)).pathname === "/api/ask");
    await waitFor(() => expect(asks()).toHaveLength(2));
    const body = JSON.parse(String((asks()[1] as [string, RequestInit])[1].body));
    expect(body.question).toBe("What is LoRA?");
  });
});

describe("DailyLimit", () => {
  const RESETS = "2026-10-26T00:00:00Z";

  it("shows the usage and when answers resume in local time; Browse passages lists results", async () => {
    const fetchMock = vi.fn(async () =>
      json({ results: [{ rank: 1, score: 0.7, passage_id: "lora-1", paper_id: "lora", title: "LoRA: Low-Rank Adaptation", section: "Our Method", page: 5, text: "LoRA freezes the pretrained weights." }] }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<DailyLimit used={50} limit={50} resetsAt={RESETS} question="What is LoRA?" />);
    expect(screen.getByText("50 / 50")).toBeInTheDocument();
    expect(screen.getByText("free requests used today")).toBeInTheDocument();
    expect(screen.getByText(new RegExp(`Answers resume at ${local(RESETS)} your time`))).toBeInTheDocument();
    expect(screen.getByText(/search and the pdf viewer keep working/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Browse passages instead" }));
    const results = await screen.findByRole("list", { name: /matching passages/i });
    expect(within(results).getByText("LoRA: Low-Rank Adaptation")).toBeInTheDocument();
    expect(within(results).getByText("Our Method · page 5")).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/api\/search$/);
    expect(JSON.parse(String(init.body))).toMatchObject({ query: "What is LoRA?" });
  });

  it("appears on the Ask screen for a daily_limit error", async () => {
    const stream = controlledStream();
    await askWith(stream);
    stream.send("error", { kind: "daily_limit", used: 50, limit: 50, resets_at: RESETS });
    stream.close();
    expect(await screen.findByText("50 / 50")).toBeInTheDocument();
  });
});

describe("RateLimited", () => {
  const UNTIL = "2026-10-25T13:30:00Z";

  it("says when to try again, in local time, for a non-daily wait", async () => {
    const stream = controlledStream();
    await askWith(stream);
    stream.send("error", { kind: "rate_limited", until: UNTIL, daily: false });
    stream.close();
    expect(await screen.findByText(`Try again at ${local(UNTIL)}`)).toBeInTheDocument();
    expect(screen.getByText(/your question is kept/i)).toBeInTheDocument();
  });

  it("shows the daily-limit state when the provider's daily quota is used up", async () => {
    const stream = controlledStream();
    await askWith(stream);
    stream.send("error", { kind: "rate_limited", until: UNTIL, daily: true });
    stream.close();
    expect(await screen.findByText("free requests used today")).toBeInTheDocument();
    expect(screen.getByText(new RegExp(`Answers resume at ${local(UNTIL)}`))).toBeInTheDocument();
  });
});

describe("HeldBack", () => {
  it("explains why and reveals the unverified answer with the invalid citation marked", async () => {
    const stream = controlledStream();
    const { user } = await askWith(stream);
    stream.send("answer", answer({
      text: NOT_FOUND, not_found: true, verified: false, fallback_reason: "invalid_citations",
      rejected_answer: "LoRA is a low-rank method [7].", warning: "server wording that is not shown",
      citations: { valid: [], invalid: [7], uncited_sentences: [] },
    }));
    stream.close();
    expect(await screen.findByText(/The model cited passage 7, but only 6 were provided/)).toBeInTheDocument();
    expect(screen.queryByText(/server wording/)).not.toBeInTheDocument();
    expect(screen.queryByText(/low-rank method/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "View the unverified answer" }));
    expect(screen.getByText("Not verified")).toBeInTheDocument();
    expect(screen.getByText(/low-rank method/)).toBeInTheDocument();
    expect(screen.getByLabelText("Citation 7: not among the provided passages")).toBeInTheDocument();
  });

  it("explains an answer that cited nothing", async () => {
    const stream = controlledStream();
    await askWith(stream);
    stream.send("answer", answer({
      text: NOT_FOUND, not_found: true, verified: false, fallback_reason: "no_citations",
      rejected_answer: "LoRA is a low-rank method.", citations: { valid: [], invalid: [], uncited_sentences: [] },
    }));
    stream.close();
    expect(await screen.findByText(/cited none of the provided passages/i)).toBeInTheDocument();
  });
});

describe("UncitedFlag", () => {
  it("underlines uncited sentences and counts them; the badge still shows", async () => {
    const stream = controlledStream();
    await askWith(stream);
    stream.send("answer", answer({
      text: "LoRA adapts large models efficiently [1]. Based on these passages, this is a strong result.",
      citations: { valid: [1], invalid: [], uncited_sentences: ["Based on these passages, this is a strong result."] },
    }));
    stream.close();
    const flagged = await screen.findByText(/this is a strong result/);
    expect(flagged.closest("[data-uncited]")).not.toBeNull();
    expect(screen.getByText(/adapts large models/).closest("[data-uncited]")).toBeNull();
    expect(screen.getByText("1 sentence has no citation")).toBeInTheDocument();
    expect(screen.getByText("All citations verified")).toBeInTheDocument();
  });
});

describe("Other states", () => {
  it("ModelUnavailable names the configured model and points to the settings", () => {
    render(<ModelUnavailable reason="bad_key" model="nvidia/nemotron-3-ultra-550b-a55b:free" />);
    expect(screen.getByText(/nvidia\/nemotron-3-ultra-550b-a55b:free/)).toBeInTheDocument();
    expect(screen.getByText(/LLM_API_KEY/)).toBeInTheDocument();
    expect(screen.getByText(/\.env/)).toBeInTheDocument();
  });

  it("PassageGone says the passage is no longer in the library", () => {
    render(<PassageGone />);
    expect(screen.getByText("This passage is no longer in your library")).toBeInTheDocument();
  });

  it("UploadInvalid shows its copy", () => {
    render(<UploadRow job={{ job_id: "j", kind: "upload", file_name: "big.pdf", phase: "failed", percent: null, outcome: "failed",
      highlights: null, paper_id: null, error: { kind: "upload_invalid", reason: "too_large" } }} />);
    expect(screen.getByText("This PDF is larger than 25 MB.")).toBeInTheDocument();
  });
});

describe("Raw errors", () => {
  it.each([
    { kind: "model_unavailable", reason: "bad_key", message: "401 sk-or-v1-secret provider said no" },
    { kind: "internal", message: "Traceback (most recent call last)" },
    { kind: "something_new", detail: "raw server text" },
  ])("never renders text from the network ($kind)", async (error) => {
    const stream = controlledStream();
    await askWith(stream);
    stream.send("error", error);
    stream.close();
    await screen.findByRole("alert");
    expect(document.body).not.toHaveTextContent(/sk-or-v1|provider said|Traceback|raw server text|something_new/);
  });
});
