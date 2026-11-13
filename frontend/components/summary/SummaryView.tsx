"use client";

import { Check } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useUsage } from "@/components/app/UsageMeter";
import { SourceViewer } from "@/components/source/SourceViewer";
import { CostButton } from "@/components/summary/CostButton";
import { PartState } from "@/components/summary/PartState";
import { SectionCard } from "@/components/summary/SectionCard";
import { TldrCard } from "@/components/summary/TldrCard";
import { TurnFailure } from "@/components/states/TurnFailure";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DailyLimit } from "@/components/states/DailyLimit";
import { apiGet } from "@/lib/api";
import { builtWithout } from "@/lib/errorKinds";
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
  const savedPart = (key: string): Part | undefined =>
    key === "tldr" ? done?.tldr : done?.sections.find((s) => s.part === key);
  const partOf = (key: string): Part | undefined =>
    running && (summary.retrying === null || summary.retrying.includes(key)) ? summary.parts[key] : savedPart(key);
  const tldrPart = partOf("tldr");
  const without = SECTIONS.filter(({ key }) => tldrPart?.built_without?.includes(key)).map(({ label }) => label);
  const showResult = running || done !== null;
  // An earlier summary is only replaced whole: a retry would mix old and new parts as if current.
  const retry = (key: string) => (stale ? undefined : () => void summary.start({ retry_parts: [key] }));
  const pending = done?.pending;
  const pendingNames = (pending?.failed_parts ?? []).map((key) => SECTIONS.find((s) => s.key === key)?.label ?? key);

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
              ) : done.verified_parts === 6 && without.length === 0 ? (
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

      {summary.phase === "none" && usage?.usage && usage.usage.remaining < summary.plan.max_requests && (
        <DailyLimit used={usage.usage.used} limit={usage.usage.limit} resetsAt={usage.usage.resets_at} question={title} what="Summaries" onOpenPassage={setOpen} />
      )}

      {summary.phase === "failed" && summary.error && (
        <TurnFailure what="Summaries" kind={summary.error.kind} fields={summary.error.fields} question={title} onRetry={() => void summary.start()} />
      )}

      {pending && !running && (
        <div role="status" className="flex flex-col gap-3 rounded-2xl border border-amber/50 p-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-text">
            {pendingNames.length > 0
              ? `The last regeneration did not finish ${pendingNames.join(", ")}, so this summary stays until it does.`
              : "The last regeneration still needs its TL;DR, so this summary stays until it has one."}
          </p>
          <CostButton
            label="Finish the regeneration"
            cost={pending.retry_parts.length}
            onClick={() => void summary.start({ retry_parts: pending.retry_parts })}
            primary={false}
          />
        </div>
      )}

      {showResult && (
        <>
          <TldrCard
            part={tldrPart}
            progress={summary.progress.tldr}
            wait={running ? summary.retry.tldr : undefined}
            passages={passages}
            onOpen={setOpen}
            note={
              without.length > 0 && (
                <div className="space-y-3">
                  <p className="text-sm text-amber">{builtWithout(without)}</p>
                  {!running && !stale && tldrPart?.state !== "failed" && tldrPart?.state !== "not_started" && (
                    <CostButton label="Rewrite the TL;DR" cost={1} onClick={() => void summary.start({ retry_parts: ["tldr"] })} primary={false} />
                  )}
                </div>
              )
            }
          >
            {tldrPart && <PartState part={tldrPart} noun="TL;DR" onRetry={running ? undefined : retry("tldr")} />}
          </TldrCard>
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {SECTIONS.map(({ key, label }) => {
              const part = partOf(key);
              return (
                <SectionCard key={key} label={label} part={part} progress={summary.progress[key]} wait={running ? summary.retry[key] : undefined} passages={passages} onOpen={setOpen}>
                  {part && <PartState part={part} noun="section" onRetry={running ? undefined : retry(key)} />}
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
