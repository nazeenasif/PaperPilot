"use client";

import { X } from "lucide-react";

import { CostButton } from "@/components/summary/CostButton";
import type { ComparisonAspect, PaperCard } from "@/lib/types";

export const ASPECTS: { key: ComparisonAspect; label: string }[] = [
  { key: "problem", label: "Problem" },
  { key: "method", label: "Method" },
  { key: "datasets", label: "Datasets" },
  { key: "results", label: "Results" },
  { key: "limitations", label: "Limitations" },
];

export const MIN_PAPERS = 2;
export const MAX_PAPERS = 4;

/** Why a comparison can't start yet, or null if it can (US3 scenario 1). */
export function selectionProblem(papers: number, aspects: number): string | null {
  if (papers < MIN_PAPERS) return `Choose at least ${MIN_PAPERS} papers.`;
  if (papers > MAX_PAPERS) return `Choose at most ${MAX_PAPERS} papers.`;
  if (aspects < 1) return "Choose at least 1 aspect.";
  return null;
}

/** Papers as chips with "+ Add paper", the fixed aspects, and the button with its cost (FR-007, FR-021). */
export function CompareForm({
  library,
  selected,
  aspects,
  onSelected,
  onAspects,
  onStart,
  canStart,
  busy,
}: {
  library: PaperCard[];
  selected: string[];
  aspects: ComparisonAspect[];
  onSelected: (ids: string[]) => void;
  onAspects: (aspects: ComparisonAspect[]) => void;
  onStart: () => void;
  /** False while a saved comparison of this selection is open: Regenerate replaces it. */
  canStart: boolean;
  busy: boolean;
}) {
  const problem = selectionProblem(selected.length, aspects.length);
  const available = library.filter((p) => !selected.includes(p.paper_id));
  const title = (id: string) => library.find((p) => p.paper_id === id)?.title ?? id;

  return (
    <section aria-label="Choose papers and aspects" className="space-y-5 rounded-2xl border border-line bg-panel p-5">
      <div className="space-y-2">
        <p className="font-mono text-xs tracking-[0.15em] text-muted-foreground">PAPERS</p>
        <div className="flex flex-wrap items-center gap-2">
          {selected.map((id) => (
            <span key={id} className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-teal/50 px-3 py-1.5 text-sm text-text">
              <span className="truncate">{title(id)}</span>
              <button
                type="button"
                aria-label={`Remove ${title(id)}`}
                onClick={() => onSelected(selected.filter((other) => other !== id))}
                className="shrink-0 rounded-full text-muted-foreground hover:text-text"
              >
                <X aria-hidden className="size-4" />
              </button>
            </span>
          ))}
          {available.length > 0 && (
            <select
              aria-label="Add paper"
              value=""
              onChange={(event) => event.target.value && onSelected([...selected, event.target.value])}
              className="max-w-full rounded-full border border-line bg-panel-2 px-3 py-1.5 text-sm text-text"
            >
              <option value="">+ Add paper</option>
              {available.map((p) => (
                <option key={p.paper_id} value={p.paper_id}>
                  {p.title}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      <fieldset className="space-y-2">
        <legend className="font-mono text-xs tracking-[0.15em] text-muted-foreground">ASPECTS</legend>
        <div className="flex flex-wrap gap-2">
          {ASPECTS.map(({ key, label }) => (
            <label key={key} className="inline-flex items-center gap-2 rounded-full border border-line px-3 py-1.5 text-sm text-text">
              <input
                type="checkbox"
                aria-label={label}
                checked={aspects.includes(key)}
                onChange={(event) =>
                  onAspects(ASPECTS.map((a) => a.key).filter((a) => (a === key ? event.target.checked : aspects.includes(a))))
                }
                className="accent-teal"
              />
              {label}
            </label>
          ))}
        </div>
      </fieldset>

      {canStart && (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <p role="status" className="text-sm text-amber">
            {problem}
          </p>
          <CostButton
            label="Compare papers"
            cost={Math.max(aspects.length, 1)}
            costNote={`uses ${aspects.length} request${aspects.length === 1 ? "" : "s"}, 1 per aspect`}
            onClick={onStart}
            disabled={problem !== null || busy}
          />
        </div>
      )}
    </section>
  );
}
