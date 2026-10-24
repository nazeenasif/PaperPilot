"use client";

import { useCallback, useRef, useState } from "react";

import { ApiError } from "@/lib/api";
import { postEventStream } from "@/lib/sse";
import type { Answer, ProgressEvent, RetryWaitEvent } from "@/lib/types";

export type TurnState = "asking" | "answered" | "failed";

/** One question and what came back for it. */
export interface AskTurn {
  id: number;
  question: string;
  state: TurnState;
  progress: ProgressEvent | null;
  retry: RetryWaitEvent | null;
  /** When the current retry wait began (Date.now()), so the countdown survives re-renders. */
  retrySince: number | null;
  answer: Answer | null;
  error: { kind: string; fields: Record<string, unknown> } | null;
}

/** Ask questions over POST /api/ask and keep the conversation's turns (FR-004, FR-006, FR-010). */
export function useAsk() {
  const [turns, setTurns] = useState<AskTurn[]>([]);
  const nextId = useRef(1);
  const busy = turns.some((turn) => turn.state === "asking");

  const update = useCallback((id: number, change: Partial<AskTurn>) => {
    setTurns((all) => all.map((turn) => (turn.id === id ? { ...turn, ...change } : turn)));
  }, []);

  const ask = useCallback(
    async (question: string) => {
      const id = nextId.current++;
      setTurns((all) => [
        ...all,
        { id, question, state: "asking", progress: null, retry: null, retrySince: null, answer: null, error: null },
      ]);
      try {
        const events = await postEventStream("/api/ask", { question });
        for await (const { event, data } of events) {
          if (event === "progress") update(id, { progress: data as ProgressEvent, retry: null });
          else if (event === "retry_wait") update(id, { retry: data as RetryWaitEvent, retrySince: Date.now() });
          else if (event === "answer") {
            update(id, { state: "answered", answer: data as Answer, progress: null, retry: null });
            return;
          } else if (event === "error") {
            const { kind, ...fields } = data as { kind: string } & Record<string, unknown>;
            update(id, { state: "failed", error: { kind, fields }, progress: null, retry: null });
            return;
          }
        }
        update(id, { state: "failed", error: { kind: "internal", fields: {} }, progress: null, retry: null });
      } catch (error) {
        const failure =
          error instanceof ApiError ? { kind: error.kind, fields: error.fields } : { kind: "internal", fields: {} };
        update(id, { state: "failed", error: failure, progress: null, retry: null });
      }
    },
    [update],
  );

  return { turns, busy, ask };
}
