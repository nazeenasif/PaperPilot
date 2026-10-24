// Server-Sent Events over fetch(): EventSource cannot POST, and POST /api/ask streams its
// progress, retry waits and final answer (research R2).

import { apiFetch, errorFrom } from "@/lib/api";

export interface StreamEvent {
  event: string;
  data: unknown;
}

function parseData(lines: string[]): unknown {
  const text = lines.join("\n");
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

/** Yield each complete event of a text/event-stream response; comments (pings) are skipped.
 *  An event still incomplete when the stream ends is dropped, as the SSE format requires. */
export async function* readEventStream(response: Response, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName = "message";
  let dataLines: string[] = [];

  try {
    while (!signal?.aborted) {
      const { done, value } = await reader.read();
      if (done) return;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split(/\r\n|\r|\n/);
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (line === "") {
          if (dataLines.length > 0) {
            yield { event: eventName, data: parseData(dataLines) };
            if (signal?.aborted) return;
          }
          eventName = "message";
          dataLines = [];
        } else if (line.startsWith(":")) {
          continue; // comment, e.g. the keep-alive ping
        } else {
          const colon = line.indexOf(":");
          const field = colon === -1 ? line : line.slice(0, colon);
          let value = colon === -1 ? "" : line.slice(colon + 1);
          if (value.startsWith(" ")) value = value.slice(1);
          if (field === "event") eventName = value;
          else if (field === "data") dataLines.push(value);
        }
      }
    }
  } finally {
    await reader.cancel().catch(() => undefined);
  }
}

/** POST a JSON body and return its event stream; a JSON error before the stream throws ApiError. */
export async function postEventStream(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<AsyncGenerator<StreamEvent>> {
  const response = await apiFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw await errorFrom(response);
  return readEventStream(response, signal);
}
