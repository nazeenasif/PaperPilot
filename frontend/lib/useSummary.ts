"use client";

import { createContext, useCallback, useContext, useEffect, useState, useSyncExternalStore } from "react";

import { ApiError, apiGet } from "@/lib/api";
import { postEventStream } from "@/lib/sse";
import type { Part, RequestPlan, RetryWaitEvent, Summary } from "@/lib/types";

/** Progress of one part while a summary runs. */
export type PartProgress = "searching" | "reading" | "generating" | "checking";

export type SummaryPhase = "loading" | "none" | "running" | "done" | "failed";

export interface SummaryState {
  phase: SummaryPhase;
  /** The saved summary, or the finished run's summary. */
  summary: Summary | null;
  /** Plan for the next run (6, or fewer for a retry). */
  plan: RequestPlan;
  /** Parts checked so far in the running run, by part name. */
  parts: Record<string, Part>;
  progress: Record<string, PartProgress>;
  retry: Record<string, { event: RetryWaitEvent; since: number }>;
  /** The parts being retried; the other saved parts stay on screen meanwhile. */
  retrying: string[] | null;
  error: { kind: string; fields: Record<string, unknown> } | null;
}

const INITIAL: SummaryState = {
  phase: "loading",
  summary: null,
  plan: { max_requests: 6 },
  parts: {},
  progress: {},
  retry: {},
  retrying: null,
  error: null,
};

/** One paper's summary state, kept outside React so a run keeps streaming into it while no page
 *  shows it. The saved summary is looked up when nothing is shown or running (0 requests). */
export class SummaryStore {
  private state: SummaryState = INITIAL;
  private readonly listeners = new Set<() => void>();
  private looking = false;
  /** Runs after every run, e.g. to refresh the request meter. */
  onSettled: (() => void) | undefined;

  constructor(readonly paperId: string) {}

  getState = (): SummaryState => this.state;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => void this.listeners.delete(listener);
  };

  private set(change: (s: SummaryState) => SummaryState): void {
    this.state = change(this.state);
    for (const listener of this.listeners) listener();
  }

  /** Look up the saved summary, unless one is on screen, a run is streaming or a lookup is out. */
  load(): void {
    if (this.looking || this.state.phase === "running" || this.state.phase === "done") return;
    this.looking = true;
    this.set(() => INITIAL);
    apiGet<Summary>(`/api/summaries/${encodeURIComponent(this.paperId)}`)
      .then((summary) => this.settleLookup(() => ({ ...INITIAL, phase: "done", summary, plan: summary.plan })))
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.kind === "not_saved") {
          const plan = (error.fields.plan as RequestPlan) ?? INITIAL.plan;
          this.settleLookup(() => ({ ...INITIAL, phase: "none", plan }));
        } else {
          const kind = error instanceof ApiError ? error.kind : "internal";
          const fields = error instanceof ApiError ? error.fields : {};
          this.settleLookup(() => ({ ...INITIAL, phase: "failed", error: { kind, fields } }));
        }
      });
  }

  /** A lookup's result counts only if no run started meanwhile. */
  private settleLookup(next: () => SummaryState): void {
    this.looking = false;
    if (this.state.phase === "loading") this.set(next);
  }

  start = async (body: { regenerate?: boolean; retry_parts?: string[] } = {}): Promise<void> => {
    this.set((s) => ({ ...s, phase: "running", parts: {}, progress: {}, retry: {}, retrying: body.retry_parts ?? null, error: null }));
    try {
      const events = await postEventStream(`/api/summaries/${encodeURIComponent(this.paperId)}`, body);
      for await (const { event, data } of events) {
        if (event === "plan") {
          this.set((s) => ({ ...s, plan: data as RequestPlan }));
        } else if (event === "progress") {
          const { part, step } = data as { part: string; step: PartProgress };
          this.set((s) => ({ ...s, progress: { ...s.progress, [part]: step } }));
        } else if (event === "retry_wait") {
          const retry = data as RetryWaitEvent & { part: string };
          this.set((s) => ({ ...s, retry: { ...s.retry, [retry.part]: { event: retry, since: Date.now() } } }));
        } else if (event === "part") {
          const part = data as Part;
          this.set((s) => {
            const retry = { ...s.retry };
            delete retry[part.part];
            return { ...s, parts: { ...s.parts, [part.part]: part }, retry };
          });
        } else if (event === "summary") {
          const summary = data as Summary;
          this.set((s) => ({ ...s, phase: "done", summary, plan: summary.plan, progress: {}, retry: {} }));
        } else if (event === "error") {
          const { kind, ...fields } = data as { kind: string } & Record<string, unknown>;
          this.set((s) => ({ ...s, phase: "failed", error: { kind, fields } }));
        }
      }
    } catch (error) {
      const failure = error instanceof ApiError ? { kind: error.kind, fields: error.fields } : { kind: "internal", fields: {} };
      this.set((s) => ({ ...s, phase: "failed", error: failure }));
    } finally {
      this.onSettled?.();
    }
  };
}

/** The summary stores by paper, kept by SummaryProvider in the layout for the whole visit. */
export const SummaryStoresContext = createContext<Map<string, SummaryStore> | null>(null);

function storeFor(stores: Map<string, SummaryStore>, paperId: string): SummaryStore {
  let store = stores.get(paperId);
  if (!store) {
    store = new SummaryStore(paperId);
    stores.set(paperId, store);
  }
  return store;
}

/** A paper's summary: the saved one (0 requests) or a run streamed part by part (FR-012, FR-016).
 *  `onSettled` runs after every run, e.g. to refresh the request meter. Inside a SummaryProvider
 *  the summary outlives the page; without one it lasts as long as the component. */
export function useSummary(paperId: string, onSettled?: () => void) {
  const shared = useContext(SummaryStoresContext);
  const [own] = useState(() => new Map<string, SummaryStore>());
  const store = storeFor(shared ?? own, paperId);
  useEffect(() => {
    store.onSettled = onSettled;
  });
  useEffect(() => store.load(), [store]);
  const state = useSyncExternalStore(store.subscribe, store.getState, store.getState);
  const start = useCallback(
    (body?: { regenerate?: boolean; retry_parts?: string[] }) => store.start(body),
    [store],
  );
  return { ...state, start };
}
