"use client";

import type { Scope } from "@/lib/useScope";

/** "Search scope · 2 of 5 papers": a checkbox per paper with its passage count (FR-007, FR-008). */
export function ScopePanel({ scope }: { scope: Scope }) {
  const { papers, selected, blocked, toggle } = scope;
  if (papers === null) return null;

  return (
    <section aria-label="Search scope" className="space-y-3">
      <p className="font-mono text-xs tracking-wide text-muted-foreground">
        Search scope · {selected.length} of {papers.length} paper{papers.length === 1 ? "" : "s"}
      </p>
      {papers.length === 0 && <p className="text-sm text-muted-foreground">Your library is empty.</p>}
      <ul className="space-y-1">
        {papers.map((paper) => {
          const id = `scope-${paper.paper_id}`;
          return (
            <li key={paper.paper_id}>
              <label
                htmlFor={id}
                className="flex cursor-pointer items-start gap-3 rounded-xl px-2 py-2 hover:bg-panel-2 focus-within:bg-panel-2"
              >
                <input
                  id={id}
                  type="checkbox"
                  checked={selected.includes(paper.paper_id)}
                  onChange={() => toggle(paper.paper_id)}
                  className="mt-1 size-4 shrink-0 accent-teal"
                />
                <span className="min-w-0">
                  <span className="block text-sm leading-snug text-text">{paper.title}</span>
                  <span className="font-mono text-xs text-muted-foreground">{paper.passage_count} passages</span>
                </span>
              </label>
            </li>
          );
        })}
      </ul>
      {blocked && (
        <p role="status" className="text-sm text-amber">
          At least one paper must stay selected, so there is something to search.
        </p>
      )}
    </section>
  );
}
