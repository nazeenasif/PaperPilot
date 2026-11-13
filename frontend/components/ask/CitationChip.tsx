import type { NumberedPassage } from "@/lib/types";

/** A numbered citation; opens the cited passage in the source viewer (FR-005, FR-012). */
export function CitationChip({
  number,
  passage,
  onOpen,
}: {
  number: number;
  passage: NumberedPassage | undefined;
  onOpen: (passage: NumberedPassage) => void;
}) {
  if (!passage) {
    // A number with no passage behind it; the engine holds such answers back, so this is rare.
    return (
      <span className="mx-0.5 inline-flex min-w-6 items-center justify-center rounded-md border border-line px-1.5 font-mono text-xs text-muted-foreground">
        {number}
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={() => onOpen(passage)}
      aria-label={`Citation ${number}: ${passage.title}, page ${passage.page}`}
      className="mx-0.5 inline-flex min-w-6 items-center justify-center rounded-md border border-amber/60 bg-amber/10 px-1.5 align-baseline font-mono text-xs font-semibold text-amber transition-colors hover:bg-amber hover:text-ink"
    >
      {number}
    </button>
  );
}
