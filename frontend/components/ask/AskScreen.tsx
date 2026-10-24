"use client";

import { useState } from "react";

import { useStatus } from "@/components/app/StatusGate";
import { useUsage } from "@/components/app/UsageMeter";
import { AnswerView } from "@/components/ask/AnswerView";
import { COMPOSER_ID, Composer } from "@/components/ask/Composer";
import { ProgressSteps } from "@/components/ask/ProgressSteps";
import { SourceViewer } from "@/components/source/SourceViewer";
import { Busy } from "@/components/states/Busy";
import { HeldBack } from "@/components/states/HeldBack";
import { NotFound } from "@/components/states/NotFound";
import { TurnFailure } from "@/components/states/TurnFailure";
import type { NumberedPassage } from "@/lib/types";
import { useAsk } from "@/lib/useAsk";

/** The Ask screen: the conversation, the working state, the composer and the source viewer
 *  opened from citation chips (User Stories 1 and 2). */
export function AskScreen() {
  const usage = useUsage();
  const { turns, busy, ask } = useAsk({
    // The meter follows each answer's figure; after a failure it asks the server (FR-024).
    onAnswer: (answer) => answer.usage && usage?.report(answer.usage),
    onFailure: () => void usage?.refresh(),
  });
  const [openPassage, setOpenPassage] = useState<NumberedPassage | null>(null);
  const connection = useStatus();
  const status = connection.kind === "status" ? connection.status : null;
  const rephrase = () => document.getElementById(COMPOSER_ID)?.focus();

  return (
    <main className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-3xl flex-col px-4 pt-8 pb-6">
      <h1 className="sr-only">Ask your papers</h1>
      <ol className="flex-1 space-y-10">
        {turns.map((turn) => (
          <li key={turn.id} className="space-y-4">
            <p className="ml-auto w-fit max-w-[85%] rounded-2xl border border-line bg-panel px-4 py-2.5 whitespace-pre-wrap text-text">
              {turn.question}
            </p>
            {turn.state === "asking" &&
              (turn.retry && turn.retrySince !== null ? (
                <Busy retry={turn.retry} since={turn.retrySince} />
              ) : (
                <ProgressSteps progress={turn.progress} retry={turn.retry} />
              ))}
            {turn.state === "answered" && turn.answer && (
              turn.answer.not_found && turn.answer.rejected_answer ? (
                <HeldBack answer={turn.answer} />
              ) : turn.answer.not_found ? (
                // Every paper is searched until scope selection exists (US4).
                <NotFound
                  sentence={turn.answer.text}
                  canSearchAll={false}
                  onSearchAll={() => void ask(turn.question)}
                  onRephrase={rephrase}
                />
              ) : (
                <AnswerView answer={turn.answer} onOpenCitation={setOpenPassage} />
              )
            )}
            {turn.state === "failed" && turn.error && (
              <TurnFailure
                kind={turn.error.kind}
                fields={turn.error.fields}
                question={turn.question}
                model={status?.model}
                dailyLimit={status?.daily_limit}
                onRetry={() => void ask(turn.question)}
                onOpenPassage={setOpenPassage}
              />
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
      {openPassage && <SourceViewer citation={openPassage} onClose={() => setOpenPassage(null)} />}
    </main>
  );
}
