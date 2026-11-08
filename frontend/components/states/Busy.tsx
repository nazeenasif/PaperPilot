"use client";

import { useEffect, useState } from "react";

import { StateCard } from "@/components/states/StateCard";
import type { RetryWaitEvent } from "@/lib/types";

const TICK_MS = 250;

function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/** The free model is rate-limited or slow: a live countdown to the next attempt (FR-023).
 *  `since` is when the wait began, so re-renders never restart the count. */
export function Busy({
  retry,
  since,
  safe = "Your question is safe.",
}: {
  retry: RetryWaitEvent;
  since: number;
  /** What is not lost while waiting. */
  safe?: string;
}) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), TICK_MS);
    return () => clearInterval(timer);
  }, []);

  const elapsed = Math.max(0, (now - since) / 1000);
  const remaining = Math.max(0, Math.ceil(retry.wait_seconds - elapsed));
  const done = retry.wait_seconds > 0 ? Math.min(1, elapsed / retry.wait_seconds) : 1;

  return (
    <StateCard label="Busy · retrying" tone="amber">
      <p role="status" aria-live="off" className="flex items-baseline gap-3">
        <span className="font-heading text-5xl font-semibold text-amber tabular-nums">{clock(remaining)}</span>
        <span className="text-muted-foreground">
          attempt {retry.attempt + 1} of {retry.max_attempts}
        </span>
      </p>
      <p className="font-heading text-lg font-semibold text-text">The free model is busy right now</p>
      <p className="text-muted-foreground">
        {safe} PaperPilot will retry automatically when the provider says it&apos;s ready.
      </p>
      <div aria-hidden className="h-1.5 overflow-hidden rounded-full bg-panel-2">
        <div className="h-full rounded-full bg-amber" style={{ width: `${done * 100}%` }} />
      </div>
    </StateCard>
  );
}
