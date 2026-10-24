import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import { postEventStream, readEventStream, type StreamEvent } from "@/lib/sse";

const encoder = new TextEncoder();

/** A Response whose body arrives in exactly these chunks. */
function streamResponse(chunks: string[], init: ResponseInit = {}): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(body, { headers: { "Content-Type": "text/event-stream" }, ...init });
}

async function collect(iterable: AsyncIterable<StreamEvent>): Promise<StreamEvent[]> {
  const events: StreamEvent[] = [];
  for await (const event of iterable) events.push(event);
  return events;
}

describe("readEventStream", () => {
  it("joins an event split across chunks and parses JSON data", async () => {
    const response = streamResponse(['event: progr', 'ess\ndata: {"step":', '"searching"}\n', "\n"]);
    expect(await collect(readEventStream(response))).toEqual([{ event: "progress", data: { step: "searching" } }]);
  });

  it("yields several events from one chunk, in order", async () => {
    const response = streamResponse([
      'event: progress\ndata: {"step":"searching"}\n\nevent: answer\ndata: {"text":"Hi [1]."}\n\n',
    ]);
    const events = await collect(readEventStream(response));
    expect(events.map((e) => e.event)).toEqual(["progress", "answer"]);
    expect(events[1]?.data).toEqual({ text: "Hi [1]." });
  });

  it("ignores keep-alive ping comments", async () => {
    const response = streamResponse([": ping\n\n", 'event: progress\ndata: {"step":"checking"}\n\n', ": ping\n\n"]);
    expect(await collect(readEventStream(response))).toEqual([{ event: "progress", data: { step: "checking" } }]);
  });

  it("accepts CRLF line endings", async () => {
    const response = streamResponse(['event: answer\r\ndata: {"ok":true}\r\n\r\n']);
    expect(await collect(readEventStream(response))).toEqual([{ event: "answer", data: { ok: true } }]);
  });

  it("joins multi-line data with newlines and defaults the event name to message", async () => {
    const response = streamResponse(['data: {"a":\ndata: 1}\n\n']);
    expect(await collect(readEventStream(response))).toEqual([{ event: "message", data: { a: 1 } }]);
  });

  it("keeps non-JSON data as text", async () => {
    const response = streamResponse(["event: note\ndata: plain words\n\n"]);
    expect(await collect(readEventStream(response))).toEqual([{ event: "note", data: "plain words" }]);
  });

  it("drops an unfinished event at the end of the stream", async () => {
    const response = streamResponse(['event: answer\ndata: {"text":"done"}\n\n', 'event: progress\ndata: {"step":"x"}']);
    expect((await collect(readEventStream(response))).map((e) => e.event)).toEqual(["answer"]);
  });

  it("stops when the signal is aborted", async () => {
    const controller = new AbortController();
    const response = streamResponse([
      'event: progress\ndata: {"step":"searching"}\n\n',
      'event: progress\ndata: {"step":"reading"}\n\n',
    ]);
    const events: StreamEvent[] = [];
    for await (const event of readEventStream(response, controller.signal)) {
      events.push(event);
      controller.abort();
    }
    expect(events).toHaveLength(1);
  });
});

describe("postEventStream", () => {
  it("posts JSON and streams the events", async () => {
    const fetchMock = vi.fn().mockResolvedValue(streamResponse(['event: answer\ndata: {"text":"ok"}\n\n']));
    vi.stubGlobal("fetch", fetchMock);
    const events = await collect(await postEventStream("/api/ask", { question: "What is LoRA?" }));
    expect(events).toEqual([{ event: "answer", data: { text: "ok" } }]);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/ask");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ question: "What is LoRA?" }));
    expect(new Headers(init.headers).get("Accept")).toBe("text/event-stream");
    expect(new Headers(init.headers).get("X-PaperPilot")).toBe("1");
  });

  it("throws an ApiError when the server answers with a JSON error before streaming", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ kind: "busy_question" }), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const error = await postEventStream("/api/ask", { question: "x" }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ kind: "busy_question", status: 409 });
  });

  it("reports a network failure as kind unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(postEventStream("/api/ask", { question: "x" })).rejects.toMatchObject({ kind: "unreachable" });
  });
});
