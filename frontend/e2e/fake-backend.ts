// A fake PaperPilot API for the smoke tests: page.route answers every request to the API's
// origin, including CORS preflights. Nothing reaches the real API or the model.

import type { Page, Route } from "@playwright/test";

import type { PaperCard, UploadJob, Usage } from "../lib/types";
import {
  ASK_EVENTS,
  JOB_SCRIPTS,
  LIBRARY_PAPERS,
  NEW_PAPER,
  PDF_LINES,
  SEARCH_RESULTS,
  STATUS,
  USAGE,
  VIEW_HIGHLIGHTED,
  VIEW_UNMARKED,
} from "./fixtures";
import { makePdf } from "./pdf";

export const API = "http://127.0.0.1:8000";

export const CORS = {
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
  /** GET /api/usage reading (default USAGE). */
  usage?: Usage;
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
    } else if (path === "/api/usage") {
      await route.fulfill({ status: 200, headers: CORS, json: options.usage ?? USAGE });
    } else if (path === "/api/search" && request.method() === "POST") {
      await route.fulfill({ status: 200, headers: CORS, json: SEARCH_RESULTS });
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

type Handler = (route: Route) => Promise<void>;

export interface FakeLibrary {
  /** Pass as `routes` to fakeBackend. */
  routes: Record<string, Handler>;
  /** X-PaperPilot header of every write. */
  writeHeaders: (string | undefined)[];
  /** File names of every upload request. */
  uploads: string[][];
}

/** A stateful fake library: uploads create jobs that move one scripted step per GET /api/jobs
 *  (the event stream ends at once, so the page falls back to polling). */
export function fakeLibrary(): FakeLibrary {
  const papers: PaperCard[] = LIBRARY_PAPERS.map((paper) => ({ ...paper }));
  const jobs: { job: UploadJob; script: Partial<UploadJob>[]; step: number }[] = [];
  const state: FakeLibrary = { routes: {}, writeHeaders: [], uploads: [] };
  const library = () => ({ papers, total_passages: papers.reduce((sum, p) => sum + p.passage_count, 0) });

  function advance() {
    for (const entry of jobs) {
      entry.step = Math.min(entry.step + 1, entry.script.length - 1);
      entry.job = { ...entry.job, ...entry.script[entry.step] };
      if (entry.job.phase !== "ready") continue;
      if (entry.job.paper_id === NEW_PAPER.paper_id && !papers.some((p) => p.paper_id === NEW_PAPER.paper_id)) {
        papers.push({ ...NEW_PAPER });
      }
      if (entry.job.outcome === "pdf_attached") {
        const paper = papers.find((p) => p.paper_id === entry.job.paper_id);
        if (paper) Object.assign(paper, { has_pdf: true, highlights: "exact" });
      }
    }
  }

  state.routes["/api/papers"] = async (route) => {
    const request = route.request();
    if (request.method() !== "POST") {
      await route.fulfill({ status: 200, headers: CORS, json: library() });
      return;
    }
    state.writeHeaders.push(request.headers()["x-paperpilot"]);
    const names = [...(request.postDataBuffer()?.toString("latin1") ?? "").matchAll(/filename="([^"]+)"/g)].map((m) => m[1] ?? "");
    state.uploads.push(names);
    const created = names.map((name, index) => {
      const job: UploadJob = {
        job_id: `job-${jobs.length + index + 1}`, kind: "upload", file_name: name, phase: "queued", percent: null,
        outcome: null, highlights: null, paper_id: null, error: null,
      };
      return { job, script: JOB_SCRIPTS[name] ?? [{ phase: "failed", outcome: "failed", error: { kind: "upload_invalid", reason: "not_pdf" } }], step: -1 };
    });
    jobs.push(...created);
    await route.fulfill({ status: 202, headers: CORS, json: { jobs: created.map(({ job }) => ({ job_id: job.job_id, file_name: job.file_name })) } });
  };
  state.routes["/api/jobs"] = async (route) => {
    advance();
    await route.fulfill({ status: 200, headers: CORS, json: { jobs: jobs.map(({ job }) => job) } });
  };
  state.routes["/api/jobs/events"] = async (route) => {
    await route.fulfill({ status: 200, headers: { ...CORS, "content-type": "text/event-stream" }, body: "" });
  };
  state.routes[`/api/papers/${NEW_PAPER.paper_id}`] = async (route) => {
    state.writeHeaders.push(route.request().headers()["x-paperpilot"]);
    const index = papers.findIndex((p) => p.paper_id === NEW_PAPER.paper_id);
    if (index >= 0) papers.splice(index, 1);
    await route.fulfill({ status: 200, headers: CORS, json: { removed_passages: NEW_PAPER.passage_count } });
  };
  return state;
}

/** Make POST /api/ask stream its events over time inside the page (page.route can only send a
 *  whole body at once): each step waits `afterMs`, then sends one event. */
export async function streamAskInPage(page: Page, steps: { afterMs: number; event: string; data: unknown }[]) {
  await page.addInitScript((plan) => {
    const original = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (!url.endsWith("/api/ask")) return original(input, init);
      const encoder = new TextEncoder();
      const body = new ReadableStream<Uint8Array>({
        async start(controller) {
          for (const step of plan) {
            await new Promise((resolve) => setTimeout(resolve, step.afterMs));
            controller.enqueue(encoder.encode(`event: ${step.event}\ndata: ${JSON.stringify(step.data)}\n\n`));
          }
          controller.close();
        },
      });
      return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
    };
  }, steps);
}
