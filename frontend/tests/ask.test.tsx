import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AskScreen } from "@/components/ask/AskScreen";
import type { Answer } from "@/lib/types";

const encoder = new TextEncoder();

/** A fetch Response whose event stream the test feeds by hand. */
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

const PASSAGES = [
  { number: 1, passage_id: "p-1", paper_id: "p", title: "LoRA: Low-Rank Adaptation", section: "Our Method", page: 5, score: 0.71, text: "x" },
  { number: 2, passage_id: "q-2", paper_id: "q", title: "Attention Is All You Need", section: "Training", page: 7, score: 0.62, text: "y" },
];

function answer(overrides: Partial<Answer> = {}): Answer {
  return {
    question: "What is LoRA?",
    standalone_question: "What is LoRA?",
    rewrite_applied: false,
    rewrite_fallback_reason: null,
    text: "LoRA is an efficient adaptation strategy [1]. It allows quick task switching [1, 2].",
    not_found: false,
    fallback_reason: null,
    warning: null,
    rejected_answer: null,
    citations: { valid: [1, 2], invalid: [], uncited_sentences: [] },
    verified: true,
    passages: PASSAGES,
    papers_read: 2,
    word_count: 14,
    llm_calls: 1,
    requests: { planned: 1, retries: 0 },
    timings: { rewrite: 0, retrieve: 0.1, generate: 8.7 },
    tokens: {},
    usage: null as unknown as Answer["usage"],
    ...overrides,
  };
}

async function ask(question: string) {
  const user = userEvent.setup();
  render(<AskScreen />);
  await user.type(screen.getByRole("textbox", { name: /ask about your papers/i }), `${question}{Enter}`);
  return user;
}

describe("Composer", () => {
  it("asks for a question instead of sending an empty one", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AskScreen />);
    await user.click(screen.getByRole("button", { name: /send question/i }));
    expect(screen.getByText(/type a question first/i)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends on Enter, adds a line on Shift+Enter, and is disabled while answering", async () => {
    const stream = controlledStream();
    const fetchMock = vi.fn().mockResolvedValue(stream.response);
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AskScreen />);
    const box = screen.getByRole("textbox", { name: /ask about your papers/i });
    await user.type(box, "What is{Shift>}{Enter}{/Shift}LoRA?");
    expect(fetchMock).not.toHaveBeenCalled();
    await user.type(box, "{Enter}");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/ask");
    expect(JSON.parse(String(init.body))).toMatchObject({ question: "What is\nLoRA?" });
    await waitFor(() => expect(box).toBeDisabled());
    expect(screen.getByRole("button", { name: /send question/i })).toBeDisabled();
    stream.send("answer", answer());
    stream.close();
    await waitFor(() => expect(box).toBeEnabled());
  });
});

describe("Progress and answer", () => {
  it("shows each step, and no answer text until the checked answer arrives", async () => {
    const stream = controlledStream();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(stream.response));
    await ask("What is LoRA?");
    stream.send("progress", { step: "searching" });
    expect(await screen.findByText("Searching your papers…")).toBeInTheDocument();
    stream.send("progress", { step: "reading", passages: 6, papers: 2 });
    expect(await screen.findByText("Reading 6 passages from 2 papers…")).toBeInTheDocument();
    stream.send("progress", { step: "generating" });
    expect(await screen.findByText("Writing the answer…")).toBeInTheDocument();
    stream.send("progress", { step: "checking" });
    expect(await screen.findByText("Checking citations…")).toBeInTheDocument();
    expect(screen.queryByText(/efficient adaptation strategy/)).not.toBeInTheDocument();

    stream.send("answer", answer());
    stream.close();
    expect(await screen.findByText(/efficient adaptation strategy/)).toBeInTheDocument();
    expect(screen.queryByText("Checking citations…")).not.toBeInTheDocument();
  });

  it("renders citation chips as labelled buttons and the verified badge", async () => {
    const stream = controlledStream();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(stream.response));
    await ask("What is LoRA?");
    stream.send("answer", answer());
    stream.close();
    const chips = await screen.findAllByRole("button", { name: /^Citation \d/ });
    expect(chips.map((c) => c.textContent)).toEqual(["1", "1", "2"]);
    expect(chips[0]).toHaveAccessibleName("Citation 1: LoRA: Low-Rank Adaptation, page 5");
    expect(chips[2]).toHaveAccessibleName("Citation 2: Attention Is All You Need, page 7");
    expect(screen.getByText("All citations verified")).toBeInTheDocument();
    expect(screen.getByText(/2 passages read · 8\.8 s/)).toBeInTheDocument();
    expect(screen.getByText("What is LoRA?")).toBeInTheDocument();
  });

  it("shows no verified badge for an unverified answer", async () => {
    const stream = controlledStream();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(stream.response));
    await ask("What is LoRA?");
    stream.send("answer", answer({ verified: false }));
    stream.close();
    await screen.findByText(/efficient adaptation strategy/);
    expect(screen.queryByText("All citations verified")).not.toBeInTheDocument();
  });

  it("shows the not-found sentence exactly as received", async () => {
    const stream = controlledStream();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(stream.response));
    await ask("What is the capital of France?");
    const notFound = "I couldn't find that in the selected papers.";
    stream.send("answer", answer({ text: notFound, not_found: true, verified: false, passages: [],
      citations: { valid: [], invalid: [], uncited_sentences: [] }, fallback_reason: "below_threshold" }));
    stream.close();
    expect(await screen.findByText(notFound)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Citation/ })).not.toBeInTheDocument();
  });

  it("never shows server text when the question fails", async () => {
    const stream = controlledStream();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(stream.response));
    await ask("What is LoRA?");
    stream.send("error", { kind: "internal", detail: "Traceback (most recent call last)" });
    stream.close();
    const alert = await screen.findByRole("alert");
    expect(alert).not.toHaveTextContent(/traceback/i);
    expect(screen.getByRole("textbox", { name: /ask about your papers/i })).toBeEnabled();
  });
});
