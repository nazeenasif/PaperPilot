import { LoaderCircle } from "lucide-react";

import type { ProgressEvent, RetryWaitEvent } from "@/lib/types";

/** Wording for each step the engine reports while answering (FR-006). */
export function progressText(progress: ProgressEvent | null): string {
  switch (progress?.step) {
    case "rewriting":
      return "Understanding your follow-up…";
    case "reading": {
      const passages = progress.passages ?? 0;
      const papers = progress.papers ?? 0;
      return `Reading ${passages} passage${passages === 1 ? "" : "s"} from ${papers} paper${papers === 1 ? "" : "s"}…`;
    }
    case "generating":
      return "Writing the answer…";
    case "checking":
      return "Checking citations…";
    case "searching":
    default:
      return "Searching your papers…";
  }
}

/** The working state shown until the checked answer arrives (no answer text is shown before). */
export function ProgressSteps({ progress, retry }: { progress: ProgressEvent | null; retry: RetryWaitEvent | null }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-2 font-mono text-sm text-teal">
      <LoaderCircle aria-hidden className="size-4 motion-safe:animate-spin" />
      <span>{retry ? "The free model is busy — retrying…" : progressText(progress)}</span>
    </div>
  );
}
