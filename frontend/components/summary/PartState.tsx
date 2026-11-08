"use client";

import { Search, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { CostButton } from "@/components/summary/CostButton";
import { PART_NOT_REPORTED, heldBackPart, partProblem } from "@/lib/errorKinds";
import { splitSegments } from "@/lib/sentences";
import type { Part } from "@/lib/types";

/** The unverified text of a held-back part, labelled, with its invalid numbers marked. */
function UnverifiedText({ text, invalid }: { text: string; invalid: Set<number> }) {
  return (
    <div className="space-y-2 rounded-xl border border-dashed border-amber/50 p-3">
      <p className="w-fit rounded-full border border-amber/50 px-2 py-0.5 font-mono text-xs text-amber">Not verified</p>
      <p className="text-sm whitespace-pre-wrap text-text">
        {splitSegments(text).map((segment, i) =>
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
  );
}

/** A summary section, TL;DR or comparison cell that is not verified, in its designed state
 *  (FR-011, FR-014). All wording is the app's own (lib/errorKinds.ts). */
export function PartState({
  part,
  noun,
  onRetry,
  retryCost = 1,
}: {
  part: Part;
  /** "section", "cell" or "TL;DR", used in the copy. */
  noun: string;
  onRetry?: () => void;
  retryCost?: number;
}) {
  const [shown, setShown] = useState(false);

  if (part.state === "not_reported") {
    return (
      <p className="flex items-start gap-2 text-muted-foreground">
        <Search aria-hidden className="mt-0.5 size-4 shrink-0" />
        <span>{PART_NOT_REPORTED}</span>
      </p>
    );
  }

  if (part.state === "held_back") {
    return (
      <div className="space-y-3">
        <p className="flex gap-2 rounded-xl border border-amber/40 bg-amber/5 px-3 py-2 text-sm text-amber">
          <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
          <span>{heldBackPart(noun, part.citations.invalid, part.passages)}</span>
        </p>
        {part.rejected_text && !shown && (
          <button
            type="button"
            onClick={() => setShown(true)}
            className="w-full rounded-xl border border-line bg-panel-2 px-3 py-2 text-sm text-text transition-colors hover:border-amber/60"
          >
            View the unverified text
          </button>
        )}
        {part.rejected_text && shown && <UnverifiedText text={part.rejected_text} invalid={new Set(part.citations.invalid)} />}
      </div>
    );
  }

  if (part.state === "failed" || part.state === "not_started") {
    const label = noun === "TL;DR" ? "Retry the TL;DR" : `Retry this ${noun}`;
    return (
      <div className="space-y-3">
        <p className="flex gap-2 text-sm text-amber">
          <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
          <span>{partProblem(part.state, part.reason, part.until ?? null)}</span>
        </p>
        {onRetry && <CostButton label={label} cost={retryCost} onClick={onRetry} primary={false} />}
      </div>
    );
  }
  return null;
}
