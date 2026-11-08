import { LoaderCircle } from "lucide-react";

import { Busy } from "@/components/states/Busy";
import { CitedText } from "@/components/summary/CitedText";
import { progressText } from "@/components/summary/SectionCard";
import type { NumberedPassage, Part, RetryWaitEvent } from "@/lib/types";
import type { PartProgress } from "@/lib/useSummary";

/** The TL;DR, written only from the verified sections and checked in code (FR-005). */
export function TldrCard({
  part,
  progress,
  wait,
  passages,
  onOpen,
  note,
  children,
}: {
  part: Part | undefined;
  progress: PartProgress | undefined;
  /** A retry wait for this part: its own countdown (FR-024). */
  wait?: { event: RetryWaitEvent; since: number };
  passages: Map<number, NumberedPassage>;
  onOpen: (passage: NumberedPassage) => void;
  /** Shown whatever the part's state, e.g. the sections it was built without. */
  note?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <section aria-label="TL;DR" className="space-y-3 rounded-2xl border border-teal/30 bg-panel p-6">
      <p className="font-mono text-xs tracking-[0.15em] text-teal">TL;DR</p>
      {!part && wait && <Busy retry={wait.event} since={wait.since} safe="Finished parts are safe." />}
      {!part && !wait && (
        <p role="status" className="flex items-center gap-2 font-mono text-sm text-teal">
          {progress && <LoaderCircle aria-hidden className="size-4 motion-safe:animate-spin" />}
          {progress ? progressText("TL;DR", progress) : "Written after the sections"}
        </p>
      )}
      {part?.state === "verified" && part.text && (
        <p className="font-heading text-xl leading-relaxed text-text">
          <CitedText text={part.text} passages={passages} onOpen={onOpen} />
        </p>
      )}
      {part && part.state !== "verified" && children}
      {note}
      {!note && (
        <p className="text-sm text-muted-foreground">
          Built only from the verified sections below; it cites their passages, never new ones.
        </p>
      )}
    </section>
  );
}
