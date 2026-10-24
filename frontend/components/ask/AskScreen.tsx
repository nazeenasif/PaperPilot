"use client";

import { useState } from "react";

import { AnswerView } from "@/components/ask/AnswerView";
import { Composer } from "@/components/ask/Composer";
import { ProgressSteps } from "@/components/ask/ProgressSteps";
import type { NumberedPassage } from "@/lib/types";
import { useAsk } from "@/lib/useAsk";

/** The Ask screen: the conversation, the working state and the composer (User Story 1). */
export function AskScreen() {
  const { turns, busy, ask } = useAsk();
  const [, setOpenPassage] = useState<NumberedPassage | null>(null);

  return (
    <main className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-3xl flex-col px-4 pt-8 pb-6">
      <h1 className="sr-only">Ask your papers</h1>
      <ol className="flex-1 space-y-10">
        {turns.map((turn) => (
          <li key={turn.id} className="space-y-4">
            <p className="ml-auto w-fit max-w-[85%] rounded-2xl border border-line bg-panel px-4 py-2.5 whitespace-pre-wrap text-text">
              {turn.question}
            </p>
            {turn.state === "asking" && <ProgressSteps progress={turn.progress} retry={turn.retry} />}
            {turn.state === "answered" && turn.answer && (
              <AnswerView answer={turn.answer} onOpenCitation={setOpenPassage} />
            )}
            {turn.state === "failed" && (
              <p role="alert" className="rounded-xl border border-amber/40 bg-panel px-4 py-3 text-text">
                PaperPilot couldn&apos;t finish this answer. Please try again in a moment.
              </p>
            )}
          </li>
        ))}
      </ol>
      <div className="sticky bottom-0 mt-8 bg-background pt-2">
        <Composer busy={busy} onAsk={ask} />
        <p className="mt-2 text-sm text-muted-foreground">
          Every answer cites the passage it came from. Click a number to see it in the paper.
        </p>
      </div>
    </main>
  );
}
