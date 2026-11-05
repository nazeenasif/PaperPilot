import { LoaderCircle } from "lucide-react";

import { UncitedFlag } from "@/components/states/UncitedFlag";
import { CitedText } from "@/components/summary/CitedText";
import type { NumberedPassage, Part } from "@/lib/types";
import type { PartProgress } from "@/lib/useSummary";

/** Progress wording for a part while it runs. */
export function progressText(label: string, step: PartProgress | undefined): string {
  const name = label === "TL;DR" ? "the TL;DR" : label.toLowerCase();
  switch (step) {
    case "searching":
      return `Searching ${name} passages`;
    case "reading":
      return `Reading ${name} passages`;
    case "generating":
      return `Writing ${name}`;
    case "checking":
      return `Checking ${name}`;
    default:
      return "Waiting";
  }
}

/** One summary section: its checked text with chips, or its progress while running. */
export function SectionCard({
  label,
  part,
  progress,
  passages,
  onOpen,
  children,
}: {
  label: string;
  part: Part | undefined;
  progress: PartProgress | undefined;
  passages: Map<number, NumberedPassage>;
  onOpen: (passage: NumberedPassage) => void;
  /** The designed state for a part that is not verified. */
  children?: React.ReactNode;
}) {
  return (
    <section aria-label={label} className="flex flex-col gap-3 rounded-2xl border border-line bg-panel p-5">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-heading text-lg font-semibold text-text">{label}</h2>
        {part && part.passages.length > 0 && (
          <span className="font-mono text-xs text-muted-foreground">{part.passages.length} passages read</span>
        )}
      </div>
      {!part && (
        <p role="status" className="flex items-center gap-2 font-mono text-sm text-teal">
          {progress && <LoaderCircle aria-hidden className="size-4 motion-safe:animate-spin" />}
          {progressText(label, progress)}
        </p>
      )}
      {part?.state === "verified" && part.text && (
        <>
          <p className="leading-relaxed text-text">
            <CitedText text={part.text} passages={passages} onOpen={onOpen} uncited={part.citations.uncited_sentences} />
          </p>
          <UncitedFlag count={part.citations.uncited_sentences.length} />
        </>
      )}
      {part && part.state !== "verified" && children}
    </section>
  );
}
