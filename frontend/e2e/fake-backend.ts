// A fake PaperPilot API for the smoke tests: page.route answers every request to the API's
// origin, including CORS preflights. Nothing reaches the real API or the model.

import type { Page, Route } from "@playwright/test";

import { ASK_EVENTS, PDF_LINES, STATUS, VIEW_HIGHLIGHTED, VIEW_UNMARKED } from "./fixtures";
import { makePdf } from "./pdf";

export const API = "http://127.0.0.1:8000";

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "content-type,x-paperpilot",
  "access-control-allow-methods": "GET,POST,DELETE",
};

/** Event-stream text for (event, data) pairs. */
export function eventStream(events: [string, unknown][]): string {
  return events.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join("");
}

export interface FakeOptions {
  /** Events streamed for POST /api/ask. */
  askEvents?: [string, unknown][];
  /** How long POST /api/ask waits before answering, to observe the working state. */
  askDelayMs?: number;
  /** Extra handlers by path, tried before the defaults. */
  routes?: Record<string, (route: Route) => Promise<void>>;
}

export interface FakeBackend {
  /** Bodies of every POST /api/ask, parsed. */
  asks: unknown[];
}

export async function fakeBackend(page: Page, options: FakeOptions = {}): Promise<FakeBackend> {
  const state: FakeBackend = { asks: [] };
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: CORS });
      return;
    }
    const custom = options.routes?.[path];
    if (custom) {
      await custom(route);
      return;
    }
    if (path === "/api/status") {
      await route.fulfill({ status: 200, headers: CORS, json: STATUS });
    } else if (path === "/api/ask" && request.method() === "POST") {
      state.asks.push(request.postDataJSON());
      if (options.askDelayMs) await new Promise((resolve) => setTimeout(resolve, options.askDelayMs));
      await route.fulfill({
        status: 200,
        headers: { ...CORS, "content-type": "text/event-stream" },
        body: eventStream(options.askEvents ?? ASK_EVENTS),
      });
    } else if (path === `/api/passages/${VIEW_HIGHLIGHTED.passage_id}`) {
      await route.fulfill({ status: 200, headers: CORS, json: VIEW_HIGHLIGHTED });
    } else if (path === `/api/passages/${VIEW_UNMARKED.passage_id}`) {
      await route.fulfill({ status: 200, headers: CORS, json: VIEW_UNMARKED });
    } else if (path === `/api/papers/${VIEW_HIGHLIGHTED.paper_id}/pdf`) {
      await route.fulfill({ status: 200, headers: { ...CORS, "content-type": "application/pdf" }, body: makePdf(PDF_LINES) });
    } else {
      await route.fulfill({ status: 404, headers: CORS, json: { kind: "not_found" } });
    }
  });
  return state;
}
