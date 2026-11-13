"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api";
import { timeAgo } from "@/lib/time";
import type { SummaryListItem } from "@/lib/types";

function statusText(item: SummaryListItem): string {
  if (item.summary.status === "current" && item.summary.created_at) return `Saved ${timeAgo(item.summary.created_at)}`;
  if (item.summary.status === "stale") return "Generated with an earlier model";
  return "Not summarized yet";
}

/** The Summarize tab: every paper with its saved summary's status (FR-001). No model request. */
export function SummarizePicker() {
  const [items, setItems] = useState<SummaryListItem[] | null>(null);
  const [problem, setProblem] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiGet<{ papers: SummaryListItem[] }>("/api/summaries")
      .then(({ papers }) => !cancelled && setItems(papers))
      .catch(() => !cancelled && setProblem(true));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="mx-auto w-full max-w-4xl space-y-8 px-4 pt-10 pb-16 sm:px-6">
      <header className="space-y-2">
        <p className="font-mono text-xs tracking-[0.2em] text-teal">SUMMARIZE</p>
        <h1 className="font-heading text-3xl font-semibold tracking-tight text-text sm:text-5xl">Summaries</h1>
        <p className="text-muted-foreground">
          A TL;DR and five cited sections per paper. A saved summary opens at no cost.
        </p>
      </header>
      {problem && (
        <p role="alert" className="rounded-xl border border-amber/40 bg-panel px-4 py-3 text-text">
          Couldn&apos;t load your papers. They will appear once PaperPilot can be reached.
        </p>
      )}
      {items && items.length === 0 && (
        <p className="text-muted-foreground">Your library is empty. Add a paper in the Library first.</p>
      )}
      {items && items.length > 0 && (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.paper_id} className="rounded-2xl border border-line bg-panel">
              <Link
                href={`/summarize/${item.paper_id}`}
                className="flex flex-col gap-1 px-5 py-4 transition-colors hover:bg-panel-2 sm:flex-row sm:items-center sm:justify-between"
              >
                <span className="font-heading font-semibold text-text">{item.title}</span>
                <span
                  className={`font-mono text-xs ${
                    item.summary.status === "current" ? "text-teal" : item.summary.status === "stale" ? "text-amber" : "text-muted-foreground"
                  }`}
                >
                  {statusText(item)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
