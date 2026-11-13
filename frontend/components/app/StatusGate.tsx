"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { GettingReady } from "@/components/states/GettingReady";
import { Unreachable } from "@/components/states/Unreachable";
import { apiGet } from "@/lib/api";
import type { Status } from "@/lib/types";

const POLL_NOT_READY_MS = 2_000;
const POLL_READY_MS = 30_000;

/** What the browser knows about the API: nothing yet, its status, or that it can't be reached. */
export type Connection = { kind: "pending" } | { kind: "status"; status: Status } | { kind: "unreachable" };

const StatusContext = createContext<Connection>({ kind: "pending" });

/** Polls GET /api/status (every 2 s until ready, then every 30 s) and shares the result. */
export function StatusProvider({ children }: { children: ReactNode }) {
  const [connection, setConnection] = useState<Connection>({ kind: "pending" });

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      let next: Connection;
      try {
        next = { kind: "status", status: await apiGet<Status>("/api/status") };
      } catch {
        next = { kind: "unreachable" };
      }
      if (cancelled) return;
      setConnection(next);
      const ready = next.kind === "status" && next.status.state === "ready";
      timer = setTimeout(poll, ready ? POLL_READY_MS : POLL_NOT_READY_MS);
    }

    void poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);

  return <StatusContext.Provider value={connection}>{children}</StatusContext.Provider>;
}

/** The latest known API status. */
export function useStatus(): Connection {
  return useContext(StatusContext);
}

/** Renders the app only when the API is ready; otherwise a designed state (FR-022). */
export function StatusGate({ children }: { children: ReactNode }) {
  const connection = useStatus();
  if (connection.kind === "unreachable") return <Unreachable />;
  if (connection.kind === "pending" || connection.status.state === "loading") return <GettingReady />;
  if (connection.status.state === "error") return <Unreachable failedToStart />;
  return <>{children}</>;
}
