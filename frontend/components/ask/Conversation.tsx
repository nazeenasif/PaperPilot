"use client";

import { AnswerView } from "@/components/ask/AnswerView";
import { ProgressSteps } from "@/components/ask/ProgressSteps";
import { SearchedAs } from "@/components/ask/SearchedAs";
import { Busy } from "@/components/states/Busy";
import { HeldBack } from "@/components/states/HeldBack";
import { NotFound } from "@/components/states/NotFound";
import { TurnFailure } from "@/components/states/TurnFailure";
import type { NumberedPassage } from "@/lib/types";
import type { AskTurn } from "@/lib/useAsk";

/** The conversation's turns: each question, then its working state, answer or designed state
 *  (User Stories 1, 4 and 5). */
export function Conversation({
  turns,
  canSearchAll,
  model,
  dailyLimit,
  onAsk,
  onSearchAll,
  onRephrase,
  onOpenPassage,
}: {
  turns: AskTurn[];
  /** True when some papers are left out of the selection. */
  canSearchAll: boolean;
  model?: string;
  dailyLimit?: number;
  onAsk: (question: string) => void;
  onSearchAll: (question: string) => void;
  onRephrase: () => void;
  onOpenPassage: (passage: NumberedPassage) => void;
}) {
  return (
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
            <div className="space-y-3">
              <SearchedAs answer={turn.answer} />
              {turn.answer.not_found && turn.answer.rejected_answer ? (
                <HeldBack answer={turn.answer} />
              ) : turn.answer.not_found ? (
                <NotFound
                  sentence={turn.answer.text}
                  canSearchAll={canSearchAll}
                  onSearchAll={() => onSearchAll(turn.question)}
                  onRephrase={onRephrase}
                />
              ) : (
                <AnswerView answer={turn.answer} onOpenCitation={onOpenPassage} />
              )}
            </div>
          )}
          {turn.state === "failed" && turn.error && (
            <TurnFailure
              kind={turn.error.kind}
              fields={turn.error.fields}
              question={turn.question}
              model={model}
              dailyLimit={dailyLimit}
              onRetry={() => onAsk(turn.question)}
              onOpenPassage={onOpenPassage}
            />
          )}
        </li>
      ))}
    </ol>
  );
}
