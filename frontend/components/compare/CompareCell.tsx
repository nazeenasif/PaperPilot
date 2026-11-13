import { UncitedFlag } from "@/components/states/UncitedFlag";
import { PartState } from "@/components/summary/PartState";
import { CitedText } from "@/components/summary/CitedText";
import type { NumberedPassage, Part } from "@/lib/types";

/** One comparison cell: its checked text with chips, or its designed state (FR-010, FR-011). */
export function CompareCell({
  part,
  passages,
  onOpen,
}: {
  part: Part | undefined;
  passages: Map<number, NumberedPassage>;
  onOpen: (passage: NumberedPassage) => void;
}) {
  if (!part) return <span className="text-sm text-muted-foreground">Waiting</span>;
  if (part.state !== "verified" || !part.text) return <PartState part={part} noun="cell" />;
  return (
    <div className="space-y-2">
      <p className="leading-relaxed text-text">
        <CitedText text={part.text} passages={passages} onOpen={onOpen} uncited={part.citations.uncited_sentences} />
      </p>
      <UncitedFlag count={part.citations.uncited_sentences.length} />
    </div>
  );
}
