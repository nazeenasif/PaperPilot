"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api";
import { postEventStream } from "@/lib/sse";
import type { Answer, ProgressEvent, RetryWaitEvent, Turn } from "@/lib/types";

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

// The API's limits on history (api/schemas.py AskIn and TurnIn).
const MAX_HISTORY_TURNS = 50;
const MAX_TURN_CHARS = 20_000;

/** The earlier answered questions and answers, oldest first, for a follow-up (FR-009).
 *  Failed and not-found turns are left out: they give a follow-up nothing to refer back to,
 *  and a history would cost a rewrite request for nothing (e.g. "Search all papers"). */
export function historyOf(turns: AskTurn[]): Turn[] {
  const history = turns.flatMap((turn): Turn[] =>
    turn.state === "answered" && turn.answer && !turn.answer.not_found
      ? [
          { role: "user", text: turn.question.slice(0, MAX_TURN_CHARS) },
          { role: "assistant", text: turn.answer.text.slice(0, MAX_TURN_CHARS) },
        ]
      : [],
  );
  return history.slice(-MAX_HISTORY_TURNS);
}

/** Ask questions over POST /api/ask and keep the conversation's turns (FR-004, FR-006, FR-009,
 *  FR-010). Follow-ups carry the earlier turns as history; `reset` starts a new conversation. */
export function useAsk(callbacks: { onAnswer?: (answer: Answer) => void; onFailure?: (kind: string) => void } = {}) {
  const [turns, setTurns] = useState<AskTurn[]>([]);
  const nextId = useRef(1);
  const callbacksRef = useRef(callbacks);
  useEffect(() => {
    callbacksRef.current = callbacks;
  });
  const busy = turns.some((turn) => turn.state === "asking");
  const turnsRef = useRef(turns);
  useEffect(() => {
    turnsRef.current = turns;
  });

  const update = useCallback((id: number, change: Partial<AskTurn>) => {
    setTurns((all) => all.map((turn) => (turn.id === id ? { ...turn, ...change } : turn)));
  }, []);

  const ask = useCallback(
    async (question: string, options: { paperIds?: string[] } = {}) => {
      const history = historyOf(turnsRef.current);
      const id = nextId.current++;
      setTurns((all) => [
        ...all,
        { id, question, state: "asking", progress: null, retry: null, retrySince: null, answer: null, error: null },
      ]);
      try {
        const events = await postEventStream("/api/ask", {
          question,
          ...(options.paperIds && { paper_ids: options.paperIds }),
          ...(history.length > 0 && { history }),
        });
        for await (const { event, data } of events) {
          if (event === "progress") update(id, { progress: data as ProgressEvent, retry: null });
          else if (event === "retry_wait") update(id, { retry: data as RetryWaitEvent, retrySince: Date.now() });
          else if (event === "answer") {
            update(id, { state: "answered", answer: data as Answer, progress: null, retry: null });
            callbacksRef.current.onAnswer?.(data as Answer);
            return;
          } else if (event === "error") {
            const { kind, ...fields } = data as { kind: string } & Record<string, unknown>;
            update(id, { state: "failed", error: { kind, fields }, progress: null, retry: null });
            callbacksRef.current.onFailure?.(kind);
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

  const reset = useCallback(() => setTurns([]), []);

  return { turns, busy, ask, reset };
}
