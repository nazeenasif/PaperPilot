"use client";

import { useCallback, useEffect, useRef, useState } from "react";

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
  error: { kind: string; fields: Record<string, unknown> } | null;
}

const INITIAL: SummaryState = {
  phase: "loading",
  summary: null,
  plan: { max_requests: 6 },
  parts: {},
  progress: {},
  retry: {},
  error: null,
};

/** A paper's summary: the saved one (0 requests) or a run streamed part by part (FR-012, FR-016).
 *  `onSettled` runs after every run, e.g. to refresh the request meter. */
export function useSummary(paperId: string, onSettled?: () => void) {
  const [state, setState] = useState<SummaryState>(INITIAL);
  const settled = useRef(onSettled);
  useEffect(() => {
    settled.current = onSettled;
  });

  useEffect(() => {
    let cancelled = false;
    setState(INITIAL);
    apiGet<Summary>(`/api/summaries/${encodeURIComponent(paperId)}`)
      .then((summary) => !cancelled && setState({ ...INITIAL, phase: "done", summary, plan: summary.plan }))
      .catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.kind === "not_saved") {
          setState({ ...INITIAL, phase: "none", plan: (error.fields.plan as RequestPlan) ?? INITIAL.plan });
        } else {
          const kind = error instanceof ApiError ? error.kind : "internal";
          setState({ ...INITIAL, phase: "failed", error: { kind, fields: error instanceof ApiError ? error.fields : {} } });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [paperId]);

  const start = useCallback(
    async (body: { regenerate?: boolean; retry_parts?: string[] } = {}) => {
      setState((s) => ({ ...s, phase: "running", parts: {}, progress: {}, retry: {}, error: null }));
      try {
        const events = await postEventStream(`/api/summaries/${encodeURIComponent(paperId)}`, body);
        for await (const { event, data } of events) {
          if (event === "plan") {
            setState((s) => ({ ...s, plan: data as RequestPlan }));
          } else if (event === "progress") {
            const { part, step } = data as { part: string; step: PartProgress };
            setState((s) => ({ ...s, progress: { ...s.progress, [part]: step } }));
          } else if (event === "retry_wait") {
            const retry = data as RetryWaitEvent & { part: string };
            setState((s) => ({ ...s, retry: { ...s.retry, [retry.part]: { event: retry, since: Date.now() } } }));
          } else if (event === "part") {
            const part = data as Part;
            setState((s) => {
              const retry = { ...s.retry };
              delete retry[part.part];
              return { ...s, parts: { ...s.parts, [part.part]: part }, retry };
            });
          } else if (event === "summary") {
            const summary = data as Summary;
            setState((s) => ({ ...s, phase: "done", summary, plan: summary.plan, progress: {}, retry: {} }));
          } else if (event === "error") {
            const { kind, ...fields } = data as { kind: string } & Record<string, unknown>;
            setState((s) => ({ ...s, phase: "failed", error: { kind, fields } }));
          }
        }
      } catch (error) {
        const failure = error instanceof ApiError ? { kind: error.kind, fields: error.fields } : { kind: "internal", fields: {} };
        setState((s) => ({ ...s, phase: "failed", error: failure }));
      } finally {
        settled.current?.();
      }
    },
    [paperId],
  );

  return { ...state, start };
}
