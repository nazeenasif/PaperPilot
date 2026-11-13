"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, apiGet } from "@/lib/api";
import { postEventStream } from "@/lib/sse";
import type { Comparison, Part, RetryWaitEvent } from "@/lib/types";
import type { PartProgress } from "@/lib/useSummary";

export type ComparisonPhase = "idle" | "loading" | "none" | "running" | "done" | "failed";

export interface ComparisonState {
  phase: ComparisonPhase;
  comparison: Comparison | null;
  /** Cells checked so far in the running run, by part name ("<aspect>:<paper_id>"). */
  parts: Record<string, Part>;
  progress: Record<string, PartProgress>;
  retry: Record<string, { event: RetryWaitEvent; since: number }>;
  /** Rows that failed in the running run, by aspect. */
  failedRows: Record<string, string>;
  /** The rows being retried; the other saved rows stay on screen meanwhile. */
  retrying: string[] | null;
  error: { kind: string; fields: Record<string, unknown> } | null;
}

const INITIAL: ComparisonState = {
  phase: "idle",
  comparison: null,
  parts: {},
  progress: {},
  retry: {},
  failedRows: {},
  retrying: null,
  error: null,
};

/** A comparison: the saved one for these papers and aspects (0 requests), or a run streamed cell by
 *  cell (FR-012, FR-016). `onSettled` runs after every run, e.g. to refresh the request meter. */
export function useComparison(paperIds: string[], aspects: string[], valid: boolean, onSettled?: () => void) {
  const [state, setState] = useState<ComparisonState>(INITIAL);
  const settled = useRef(onSettled);
  useEffect(() => {
    settled.current = onSettled;
  });
  const papersKey = paperIds.join(",");
  const aspectsKey = aspects.join(",");

  useEffect(() => {
    if (!valid) {
      setState(INITIAL);
      return;
    }
    let cancelled = false;
    setState({ ...INITIAL, phase: "loading" });
    const query = new URLSearchParams({ papers: papersKey, aspects: aspectsKey });
    apiGet<Comparison>(`/api/comparisons?${query}`)
      .then((comparison) => !cancelled && setState({ ...INITIAL, phase: "done", comparison }))
      .catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.kind === "not_saved") {
          setState({ ...INITIAL, phase: "none" });
        } else {
          const kind = error instanceof ApiError ? error.kind : "internal";
          setState({ ...INITIAL, phase: "failed", error: { kind, fields: error instanceof ApiError ? error.fields : {} } });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [papersKey, aspectsKey, valid]);

  const start = useCallback(
    async (body: { regenerate?: boolean; retry_aspects?: string[] } = {}) => {
      setState((s) => ({
        ...s,
        phase: "running",
        parts: {},
        progress: {},
        retry: {},
        failedRows: {},
        retrying: body.retry_aspects ?? null,
        error: null,
      }));
      try {
        const payload = { paper_ids: papersKey.split(","), aspects: aspectsKey.split(","), ...body };
        const events = await postEventStream("/api/comparisons", payload);
        for await (const { event, data } of events) {
          if (event === "progress") {
            const { part, step } = data as { part: string; step: PartProgress };
            setState((s) => ({ ...s, progress: { ...s.progress, [part]: step } }));
          } else if (event === "retry_wait") {
            const retry = data as RetryWaitEvent & { part: string };
            setState((s) => ({ ...s, retry: { ...s.retry, [retry.part]: { event: retry, since: Date.now() } } }));
          } else if (event === "part") {
            const part = data as Part;
            const aspect = part.part.split(":")[0] ?? "";
            setState((s) => {
              const retry = { ...s.retry };
              delete retry[aspect];
              return { ...s, parts: { ...s.parts, [part.part]: part }, retry };
            });
          } else if (event === "row_failed") {
            const { aspect, reason } = data as { aspect: string; reason: string };
            setState((s) => ({ ...s, failedRows: { ...s.failedRows, [aspect]: reason } }));
          } else if (event === "comparison") {
            setState((s) => ({ ...s, phase: "done", comparison: data as Comparison, progress: {}, retry: {}, retrying: null }));
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
    [papersKey, aspectsKey],
  );

  return { ...state, start };
}
