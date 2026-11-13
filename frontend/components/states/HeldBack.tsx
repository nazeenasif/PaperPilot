"use client";

import { TriangleAlert } from "lucide-react";
import { useState } from "react";

import { StateCard } from "@/components/states/StateCard";
import { heldBackReason } from "@/lib/errorKinds";
import { splitSegments } from "@/lib/sentences";
import type { Answer } from "@/lib/types";

/** The model cited passages it wasn't given (or none): the not-found sentence, why, and the
 *  original text on request, clearly unverified (FR-005, US5 scenario 6). */
export function HeldBack({ answer }: { answer: Answer }) {
  const [shown, setShown] = useState(false);
  const invalid = new Set(answer.citations.invalid);

  return (
    <StateCard label="Answer held back">
      <p className="font-heading text-lg font-semibold text-text">{answer.text}</p>
      <p className="flex gap-2 rounded-xl border border-amber/40 bg-amber/5 px-4 py-3 text-amber">
        <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
        <span>{heldBackReason(answer.citations.invalid, answer.passages.length)}</span>
      </p>
      {!shown && answer.rejected_answer && (
        <button
          type="button"
          onClick={() => setShown(true)}
          className="w-full rounded-xl border border-line bg-panel-2 px-4 py-3 text-text transition-colors hover:border-amber/60"
        >
          View the unverified answer
        </button>
      )}
      {shown && answer.rejected_answer && (
        <div className="space-y-2 rounded-xl border border-dashed border-amber/50 p-4">
          <p className="w-fit rounded-full border border-amber/50 px-2 py-0.5 font-mono text-xs text-amber">Not verified</p>
          <p className="whitespace-pre-wrap text-text">
            {splitSegments(answer.rejected_answer).map((segment, i) =>
              segment.kind === "text" ? (
                <span key={i}>{segment.text}</span>
              ) : (
                <span key={i}>
                  {segment.numbers.map((number) =>
                    invalid.has(number) ? (
                      <mark
                        key={number}
                        aria-label={`Citation ${number}: not among the provided passages`}
                        className="mx-0.5 rounded border border-amber bg-transparent px-1 font-mono text-xs text-amber line-through"
                      >
                        {number}
                      </mark>
                    ) : (
                      <span key={number} className="mx-0.5 rounded border border-line px-1 font-mono text-xs text-muted-foreground">
                        {number}
                      </span>
                    ),
                  )}
                </span>
              ),
            )}
          </p>
        </div>
      )}
    </StateCard>
  );
}
