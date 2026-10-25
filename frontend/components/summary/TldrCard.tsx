import { LoaderCircle } from "lucide-react";

import { CitedText } from "@/components/summary/CitedText";
import { progressText } from "@/components/summary/SectionCard";
import type { NumberedPassage, Part } from "@/lib/types";
import type { PartProgress } from "@/lib/useSummary";

/** The TL;DR, written only from the verified sections and checked in code (FR-005). */
export function TldrCard({
  part,
  progress,
  passages,
  onOpen,
  children,
}: {
  part: Part | undefined;
  progress: PartProgress | undefined;
  passages: Map<number, NumberedPassage>;
  onOpen: (passage: NumberedPassage) => void;
  children?: React.ReactNode;
}) {
  return (
    <section aria-label="TL;DR" className="space-y-3 rounded-2xl border border-teal/30 bg-panel p-6">
      <p className="font-mono text-xs tracking-[0.15em] text-teal">TL;DR</p>
      {!part && (
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
      <p className="text-sm text-muted-foreground">
        Built only from the verified sections below; it cites their passages, never new ones.
      </p>
    </section>
  );
}
