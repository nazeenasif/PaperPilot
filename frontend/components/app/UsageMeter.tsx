"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { useStatus } from "@/components/app/StatusGate";
import { DailyLimit } from "@/components/states/DailyLimit";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { apiGet } from "@/lib/api";
import type { Usage } from "@/lib/types";

/** How often GET /api/usage is read while the page is open (FR-024). */
export const USAGE_REFRESH_MS = 60_000;
/** At or below this many remaining requests the count turns amber. */
export const LOW_REMAINING = 5;

interface UsageContextValue {
  usage: Usage | null;
  /** Adopt the figure carried by an answer. */
  report: (usage: Usage) => void;
  /** Read the figure from the server now (e.g. after a failed question). */
  refresh: () => Promise<void>;
}

const UsageContext = createContext<UsageContextValue | null>(null);

/** Today's model requests: read when the API is ready, every 60 s, and after each answer. */
export function UsageProvider({ children }: { children: ReactNode }) {
  const connection = useStatus();
  const ready = connection.kind === "status" && connection.status.state === "ready";
  const [usage, setUsage] = useState<Usage | null>(null);

  const refresh = useCallback(async () => {
    try {
      setUsage(await apiGet<Usage>("/api/usage"));
    } catch {
      // Keep the last figure; the status gate reports an unreachable server.
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    void refresh();
    const timer = setInterval(() => void refresh(), USAGE_REFRESH_MS);
    return () => clearInterval(timer);
  }, [ready, refresh]);

  const value = useMemo(() => ({ usage, report: setUsage, refresh }), [usage, refresh]);
  return <UsageContext.Provider value={value}>{children}</UsageContext.Provider>;
}

/** The shared usage, or null outside a UsageProvider. */
export function useUsage(): UsageContextValue | null {
  return useContext(UsageContext);
}

/** "Requests today 34 / 50": amber when few remain; at the limit it opens the daily-limit state. */
export function UsageMeter() {
  const context = useUsage();
  const [open, setOpen] = useState(false);
  const usage = context?.usage;
  if (!usage) return null;

  const atLimit = usage.used >= usage.limit;
  const low = usage.remaining <= LOW_REMAINING;
  const count = (
    <>
      <span className="text-muted-foreground max-sm:sr-only">Requests today</span>{" "}
      <span className={low ? "text-amber" : "text-text"}>
        {usage.used} / {usage.limit}
      </span>
    </>
  );
  const chip = "rounded-lg border border-line bg-panel px-3 py-1 font-mono text-xs whitespace-nowrap";

  if (!atLimit) {
    return (
      <span role="status" aria-label="Requests today" className={chip}>
        {count}
      </span>
    );
  }
  return (
    <>
      <button
        type="button"
        aria-label={`Requests today ${usage.used} / ${usage.limit}: daily limit reached`}
        onClick={() => setOpen(true)}
        className={`${chip} border-amber/60 hover:bg-panel-2`}
      >
        {count}
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="border-line bg-ink p-0 sm:max-w-md">
          <DialogTitle className="sr-only">Daily limit reached</DialogTitle>
          <DailyLimit used={usage.used} limit={usage.limit} resetsAt={usage.resets_at} />
        </DialogContent>
      </Dialog>
    </>
  );
}
