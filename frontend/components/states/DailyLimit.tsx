"use client";

import { useState, type FormEvent } from "react";

import { StateCard } from "@/components/states/StateCard";
import { apiPost } from "@/lib/api";
import { localTime } from "@/lib/errorKinds";
import type { NumberedPassage, SearchResult } from "@/lib/types";

type Browse = { state: "idle" } | { state: "loading" } | { state: "done"; results: SearchResult[] } | { state: "failed" };

/** Today's free requests are used up: when answers resume, and passages to browse meanwhile,
 *  since search and the viewer need no model (FR-026, FR-027). */
export function DailyLimit({
  used,
  limit,
  resetsAt,
  question,
  onOpenPassage,
  what = "Answers",
}: {
  /** What stops until the reset: "Answers", "Summaries" or "Comparisons". */
  what?: string;
  used?: number;
  limit?: number;
  resetsAt: string;
  /** The question that hit the limit; without one, a search box is shown. */
  question?: string;
  onOpenPassage?: (passage: NumberedPassage) => void;
}) {
  const [browse, setBrowse] = useState<Browse>({ state: "idle" });
  const [query, setQuery] = useState(question ?? "");

  async function search(event?: FormEvent) {
    event?.preventDefault();
    if (!query.trim()) return;
    setBrowse({ state: "loading" });
    try {
      const { results } = await apiPost<{ results: SearchResult[] }>("/api/search", { query: query.trim() });
      setBrowse({ state: "done", results });
    } catch {
      setBrowse({ state: "failed" });
    }
  }

  return (
    <StateCard label="Daily limit" alert>
      <div className="flex items-center gap-4">
        <span aria-hidden className="size-14 shrink-0 rounded-full border-[6px] border-amber" />
        <div>
          <p className="font-heading text-3xl font-semibold text-text">{limit !== undefined ? `${used ?? limit} / ${limit}` : "All"}</p>
          <p className="text-sm text-muted-foreground">free requests used today</p>
        </div>
      </div>
      <p className="text-text">
        {what} resume at {localTime(resetsAt)} your time. Search and the PDF viewer keep working.
      </p>
      {question === undefined && (
        <form onSubmit={search} className="flex gap-2">
          <input
            aria-label="Search passages"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search your papers…"
            className="min-w-0 flex-1 rounded-xl border border-line bg-panel-2 px-3 py-2 text-text placeholder:text-muted-foreground"
          />
        </form>
      )}
      <button
        type="button"
        onClick={() => void search()}
        disabled={browse.state === "loading"}
        className="w-full rounded-xl border border-line bg-panel-2 px-4 py-3 text-text transition-colors hover:border-teal/60 disabled:opacity-60"
      >
        Browse passages instead
      </button>
      {browse.state === "loading" && <p className="text-sm text-muted-foreground">Searching your papers…</p>}
      {browse.state === "failed" && <p className="text-sm text-amber">The search didn&apos;t work. Try again in a moment.</p>}
      {browse.state === "done" && browse.results.length === 0 && (
        <p className="text-sm text-muted-foreground">No passages matched. Try other words.</p>
      )}
      {browse.state === "done" && browse.results.length > 0 && (
        <ol aria-label="Matching passages" className="space-y-3">
          {browse.results.map((result) => (
            <li key={result.passage_id} className="rounded-xl border border-line bg-panel-2 p-3">
              <p className="font-medium text-text">{result.title}</p>
              <p className="font-mono text-xs text-muted-foreground">
                {result.section} · page {result.page}
              </p>
              <p className="mt-1 line-clamp-3 text-sm text-text">{result.text}</p>
              {onOpenPassage && (
                <button
                  type="button"
                  onClick={() => onOpenPassage({ ...result, number: result.rank })}
                  className="mt-2 text-sm text-teal underline-offset-4 hover:underline"
                >
                  Open in the paper
                </button>
              )}
            </li>
          ))}
        </ol>
      )}
    </StateCard>
  );
}
