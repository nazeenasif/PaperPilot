"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiGet } from "@/lib/api";
import { getEventStream } from "@/lib/sse";
import type { UploadJob } from "@/lib/types";

/** How often /api/jobs is polled when the event stream can't be used. */
export const POLL_MS = 1_000;

function finished(job: Pick<UploadJob, "phase">): boolean {
  return job.phase === "ready" || job.phase === "failed";
}

/** Upload and re-process jobs, live from GET /api/jobs/events; falls back to polling GET
 *  /api/jobs when the stream fails or ends (FR-017). `onFinished` runs once per job that
 *  finishes while the page is open. */
export function useJobs(onFinished?: (job: UploadJob) => void) {
  const [jobs, setJobs] = useState<UploadJob[]>([]);
  const known = useRef(new Map<string, UploadJob>());
  const onFinishedRef = useRef(onFinished);
  useEffect(() => {
    onFinishedRef.current = onFinished;
  });

  const merge = useCallback((job: UploadJob, notify = true) => {
    const before = known.current.get(job.job_id);
    known.current.set(job.job_id, { ...before, ...job });
    setJobs([...known.current.values()]);
    if (notify && finished(job) && !(before && finished(before))) onFinishedRef.current?.(job);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const { jobs: snapshot } = await apiGet<{ jobs: UploadJob[] }>("/api/jobs");
        if (controller.signal.aborted) return;
        for (const job of snapshot) merge(job);
      } catch {
        // Unreachable for now: keep polling; the status gate shows the outage.
      }
      if (!controller.signal.aborted) timer = setTimeout(poll, POLL_MS);
    }

    async function follow() {
      try {
        const { jobs: snapshot } = await apiGet<{ jobs: UploadJob[] }>("/api/jobs");
        if (controller.signal.aborted) return;
        for (const job of snapshot) merge(job, false);
      } catch {
        // The stream (or polling) will bring the jobs.
      }
      try {
        const events = await getEventStream("/api/jobs/events", controller.signal);
        for await (const { event, data } of events) {
          if (event === "job") merge(data as UploadJob);
        }
      } catch {
        // Fall through to polling.
      }
      if (!controller.signal.aborted) void poll();
    }

    void follow();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [merge]);

  /** Show rows for just-created jobs at once, before their first event arrives. */
  const track = useCallback(
    (created: { job_id: string; file_name: string }[]) => {
      for (const { job_id, file_name } of created) {
        if (known.current.has(job_id)) continue;
        merge(
          { job_id, file_name, kind: "upload", phase: "queued", percent: null, outcome: null, highlights: null, paper_id: null, error: null },
          false,
        );
      }
    },
    [merge],
  );

  return { jobs, track };
}
