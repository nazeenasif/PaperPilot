"use client";

import { Check } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useUsage } from "@/components/app/UsageMeter";
import { SourceViewer } from "@/components/source/SourceViewer";
import { CostButton } from "@/components/summary/CostButton";
import { SectionCard } from "@/components/summary/SectionCard";
import { TldrCard } from "@/components/summary/TldrCard";
import { TurnFailure } from "@/components/states/TurnFailure";
import { apiGet } from "@/lib/api";
import type { NumberedPassage, Part, SummaryListItem } from "@/lib/types";
import { useSummary } from "@/lib/useSummary";

const SECTIONS: { key: string; label: string }[] = [
  { key: "problem", label: "Problem" },
  { key: "method", label: "Method" },
  { key: "data", label: "Data" },
  { key: "results", label: "Results" },
  { key: "limitations", label: "Limitations" },
];

/** Placeholder for a part that is not verified; the designed states come with US4. */
function UnverifiedPart({ part }: { part: Part }) {
  return <p className="text-muted-foreground">{part.state.replace("_", " ")}</p>;
}

/** One paper's summary: cost and start, per-part progress, then the TL;DR and five checked
 *  sections whose citations open the source viewer (User Story 1). */
export function SummaryView({ paperId }: { paperId: string }) {
  const usage = useUsage();
  const summary = useSummary(paperId, () => void usage?.refresh());
  const [open, setOpen] = useState<NumberedPassage | null>(null);
  const [paper, setPaper] = useState<{ title: string; arxiv_id: string | null } | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiGet<{ papers: SummaryListItem[] }>("/api/summaries")
      .then(({ papers }) => {
        const found = papers.find((p) => p.paper_id === paperId);
        if (!cancelled && found) setPaper({ title: found.title, arxiv_id: found.arxiv_id });
      })
      .catch(() => undefined); // the title also arrives with the summary
    return () => {
      cancelled = true;
    };
  }, [paperId]);

  const done = summary.summary;
  const running = summary.phase === "running";
  const title = done?.title ?? paper?.title ?? "Summary";
  const arxiv = done?.arxiv_id ?? paper?.arxiv_id;
  const passages = useMemo(() => new Map((done?.passages ?? []).map((p) => [p.number, p])), [done]);
  const partOf = (key: string): Part | undefined =>
    running ? summary.parts[key] : key === "tldr" ? done?.tldr : done?.sections.find((s) => s.part === key);
  const showResult = running || done !== null;

  return (
    <main className="mx-auto w-full max-w-6xl space-y-8 px-4 pt-10 pb-16 sm:px-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0 space-y-2">
          <p className="font-mono text-xs tracking-[0.2em] text-teal">SUMMARY{arxiv ? ` · arXiv ${arxiv}` : ""}</p>
          <h1 className="font-heading text-3xl font-semibold tracking-tight text-text sm:text-5xl">{title}</h1>
          {done && !running && (
            <p className="flex flex-wrap items-center gap-3 text-sm">
              {done.verified_parts === 6 ? (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-teal/50 px-3 py-1 text-teal">
                  <Check aria-hidden className="size-4" /> All citations verified
                </span>
              ) : (
                <span className="rounded-full border border-line px-3 py-1 text-muted-foreground">
                  {done.verified_parts} of 6 parts verified
                </span>
              )}
            </p>
          )}
        </div>
        {summary.phase === "none" && (
          <CostButton label="Summarize this paper" cost={summary.plan.max_requests} onClick={() => void summary.start()} />
        )}
      </header>

      {summary.phase === "failed" && summary.error && (
        <TurnFailure kind={summary.error.kind} fields={summary.error.fields} question={title} onRetry={() => void summary.start()} />
      )}

      {showResult && (
        <>
          <TldrCard part={partOf("tldr")} progress={summary.progress.tldr} passages={passages} onOpen={setOpen}>
            <UnverifiedPart part={partOf("tldr") as Part} />
          </TldrCard>
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {SECTIONS.map(({ key, label }) => {
              const part = partOf(key);
              return (
                <SectionCard key={key} label={label} part={part} progress={summary.progress[key]} passages={passages} onOpen={setOpen}>
                  {part && <UnverifiedPart part={part} />}
                </SectionCard>
              );
            })}
          </div>
          <p className="text-sm text-muted-foreground">
            Each section was retrieved, written and checked on its own. Click any number to open the passage in the PDF.
          </p>
        </>
      )}
      {open && <SourceViewer citation={open} onClose={() => setOpen(null)} />}
    </main>
  );
}
