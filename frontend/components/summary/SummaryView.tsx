"use client";

import { Check } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useUsage } from "@/components/app/UsageMeter";
import { SourceViewer } from "@/components/source/SourceViewer";
import { CostButton } from "@/components/summary/CostButton";
import { SectionCard } from "@/components/summary/SectionCard";
import { TldrCard } from "@/components/summary/TldrCard";
import { TurnFailure } from "@/components/states/TurnFailure";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { apiGet } from "@/lib/api";
import { timeAgo } from "@/lib/time";
import type { NumberedPassage, Part, StaleReason, SummaryListItem } from "@/lib/types";
import { useSummary } from "@/lib/useSummary";

const SECTIONS: { key: string; label: string }[] = [
  { key: "problem", label: "Problem" },
  { key: "method", label: "Method" },
  { key: "data", label: "Data" },
  { key: "results", label: "Results" },
  { key: "limitations", label: "Limitations" },
];

const STALE: Record<StaleReason, string> = {
  model_changed: "Generated with an earlier model — regenerate for a current summary.",
  instructions_changed: "Generated with earlier summary instructions — regenerate for a current summary.",
  passages_changed: "Generated before this paper was re-processed — regenerate for a current summary.",
};

/** Placeholder for a part that is not verified; the designed states come with US4. A failed
 *  part can be retried on its own (FR-020). */
function UnverifiedPart({ part, onRetry }: { part: Part; onRetry?: () => void }) {
  return (
    <div className="space-y-3">
      <p className="text-muted-foreground">{part.state.replace("_", " ")}</p>
      {onRetry && (part.state === "failed" || part.state === "not_started") && (
        <CostButton label="Retry this section" cost={2} onClick={onRetry} primary={false} />
      )}
    </div>
  );
}

/** One paper's summary: saved (0 requests) or generated with its cost shown first, per-part
 *  progress, then the TL;DR and five checked sections whose citations open the source viewer
 *  (User Stories 1 and 2). */
export function SummaryView({ paperId }: { paperId: string }) {
  const usage = useUsage();
  const summary = useSummary(paperId, () => void usage?.refresh());
  const [open, setOpen] = useState<NumberedPassage | null>(null);
  const [confirming, setConfirming] = useState(false);
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
  const stale = done?.status === "stale";
  const passages = useMemo(() => new Map((done?.passages ?? []).map((p) => [p.number, p])), [done]);
  const partOf = (key: string): Part | undefined =>
    running ? summary.parts[key] : key === "tldr" ? done?.tldr : done?.sections.find((s) => s.part === key);
  const showResult = running || done !== null;
  const retry = (key: string) => () => void summary.start({ retry_parts: [key] });

  return (
    <main className="mx-auto w-full max-w-6xl space-y-8 px-4 pt-10 pb-16 sm:px-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0 space-y-2">
          <p className="font-mono text-xs tracking-[0.2em] text-teal">SUMMARY{arxiv ? ` · arXiv ${arxiv}` : ""}</p>
          <h1 className="font-heading text-3xl font-semibold tracking-tight text-text sm:text-5xl">{title}</h1>
          {done && !running && (
            <p className="flex flex-wrap items-center gap-3 text-sm">
              {stale ? (
                <span className="rounded-full border border-amber/50 px-3 py-1 text-amber">
                  {STALE[done.stale_reason ?? "model_changed"]}
                </span>
              ) : done.verified_parts === 6 ? (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-teal/50 px-3 py-1 text-teal">
                  <Check aria-hidden className="size-4" /> All citations verified
                </span>
              ) : (
                <span className="rounded-full border border-line px-3 py-1 text-muted-foreground">
                  {done.verified_parts} of 6 parts verified
                </span>
              )}
              {!stale && (
                <span className="font-mono text-xs text-muted-foreground">
                  Saved {timeAgo(done.created_at)} · reopening cost 0 requests
                </span>
              )}
            </p>
          )}
        </div>
        {summary.phase === "none" && (
          <CostButton label="Summarize this paper" cost={summary.plan.max_requests} onClick={() => void summary.start()} />
        )}
        {done && !running && (
          <CostButton label="Regenerate summary" cost={6} onClick={() => setConfirming(true)} primary={false} />
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
                  {part && <UnverifiedPart part={part} onRetry={running ? undefined : retry(key)} />}
                </SectionCard>
              );
            })}
          </div>
          <p className="text-sm text-muted-foreground">
            Each section was retrieved, written and checked on its own. Click any number to open the passage in the PDF.
          </p>
        </>
      )}

      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent className="border-line bg-panel">
          <DialogHeader>
            <DialogTitle className="font-heading text-text">Regenerate this summary?</DialogTitle>
            <DialogDescription>
              It uses 6 requests{usage?.usage ? ` (${usage.usage.remaining} left today)` : ""}. The saved summary stays
              until the new one is complete.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <button type="button" className="rounded-xl border border-line px-4 py-2.5 text-text hover:bg-panel-2">
                Cancel
              </button>
            </DialogClose>
            <button
              type="button"
              onClick={() => {
                setConfirming(false);
                void summary.start({ regenerate: true });
              }}
              className="rounded-xl bg-teal px-4 py-2.5 font-medium text-ink hover:bg-teal/85"
            >
              Regenerate
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {open && <SourceViewer citation={open} onClose={() => setOpen(null)} />}
    </main>
  );
}
