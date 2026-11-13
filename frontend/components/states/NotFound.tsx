import { Search } from "lucide-react";

import { StateButton, StateCard } from "@/components/states/StateCard";
import { NOT_FOUND_SENTENCE } from "@/lib/errorKinds";

/** Nothing relevant in the selected papers, with ways forward (FR-022, US5 scenario 1). */
export function NotFound({
  sentence = NOT_FOUND_SENTENCE,
  canSearchAll,
  onSearchAll,
  onRephrase,
}: {
  sentence?: string;
  /** True when some papers are left out of the search, so searching all could help. */
  canSearchAll: boolean;
  onSearchAll: () => void;
  onRephrase: () => void;
}) {
  return (
    <StateCard label="Not found">
      <span className="flex size-10 items-center justify-center rounded-xl bg-panel-2 text-text">
        <Search aria-hidden className="size-5" />
      </span>
      <p className="font-heading text-lg font-semibold text-text">{sentence}</p>
      <p className="text-muted-foreground">PaperPilot only answers from your library, so it won&apos;t guess. You could:</p>
      <div className="flex flex-wrap gap-2">
        {canSearchAll && <StateButton onClick={onSearchAll}>Search all papers</StateButton>}
        <StateButton onClick={onRephrase}>Rephrase more specifically</StateButton>
      </div>
    </StateCard>
  );
}
