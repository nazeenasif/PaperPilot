"use client";

import { useEffect, useMemo, useState } from "react";

import { useUsage } from "@/components/app/UsageMeter";
import { ASPECTS, CompareForm, selectionProblem } from "@/components/compare/CompareForm";
import { CompareTable } from "@/components/compare/CompareTable";
import { SourceViewer } from "@/components/source/SourceViewer";
import { DailyLimit } from "@/components/states/DailyLimit";
import { TurnFailure } from "@/components/states/TurnFailure";
import { CostButton } from "@/components/summary/CostButton";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { apiGet } from "@/lib/api";
import { timeAgo } from "@/lib/time";
import type { ComparisonAspect, NumberedPassage, PaperCard, StaleReason } from "@/lib/types";
import { useComparison } from "@/lib/useComparison";

const STALE: Record<StaleReason, string> = {
  model_changed: "Generated with an earlier model — regenerate for a current comparison.",
  instructions_changed: "Generated with earlier instructions — regenerate for a current comparison.",
  passages_changed: "Generated before one of these papers was re-processed — regenerate for a current comparison.",
};

/** The Compare screen: choose 2-4 papers and the aspects, see the cost, run, and read a table whose
 *  cell citations open the source viewer (User Story 3). */
export function CompareView() {
  const usage = useUsage();
  const [library, setLibrary] = useState<PaperCard[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [aspects, setAspects] = useState<ComparisonAspect[]>(ASPECTS.map((a) => a.key));
  const [open, setOpen] = useState<NumberedPassage | null>(null);
  const [confirming, setConfirming] = useState(false);
  const valid = selectionProblem(selected.length, aspects.length) === null;
  const compare = useComparison(selected, aspects, valid, () => void usage?.refresh());

  useEffect(() => {
    let cancelled = false;
    apiGet<{ papers: PaperCard[] }>("/api/papers")
      .then(({ papers }) => !cancelled && setLibrary(papers))
      .catch(() => undefined); // the form stays empty and the failure states cover the rest
    return () => {
      cancelled = true;
    };
  }, []);

  const done = compare.comparison;
  const running = compare.phase === "running";
  const stale = done?.status === "stale";
  const pending = done?.pending;
  const passages = useMemo(() => new Map((done?.passages ?? []).map((p) => [p.number, p])), [done]);
  const savedRows = useMemo(() => new Map((done?.rows ?? []).map((row) => [row.aspect as string, row])), [done]);
  const labelOf = (key: string) => ASPECTS.find((a) => a.key === key)?.label ?? key;
  const papers =
    done?.papers ??
    selected.flatMap((id, i) => {
      const paper = library.find((p) => p.paper_id === id);
      return paper ? [{ paper_id: id, title: paper.title, arxiv_id: paper.arxiv_id, label: `P${i + 1}` }] : [];
    });
  const showTable = running || done !== null;

  return (
    <main className="mx-auto w-full max-w-6xl space-y-8 px-4 pt-10 pb-16 sm:px-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0 space-y-2">
          <p className="font-mono text-xs tracking-[0.2em] text-teal">COMPARE</p>
          <h1 className="font-heading text-3xl font-semibold tracking-tight text-text sm:text-5xl">Compare papers</h1>
          {done && !running && (
            <p className="flex flex-wrap items-center gap-3 text-sm">
              {stale && (
                <span className="rounded-full border border-amber/50 px-3 py-1 text-amber">{STALE[done.stale_reason ?? "model_changed"]}</span>
              )}
              {!stale && (
                <span className="font-mono text-xs text-muted-foreground">
                  Saved {timeAgo(done.created_at)} · reopening cost 0 requests
                </span>
              )}
            </p>
          )}
        </div>
        {done && !running && (
          <CostButton label="Regenerate comparison" cost={aspects.length} onClick={() => setConfirming(true)} primary={false} />
        )}
      </header>

      <CompareForm
        library={library}
        selected={selected}
        aspects={aspects}
        onSelected={setSelected}
        onAspects={setAspects}
        onStart={() => void compare.start()}
        canStart={!done && !running}
        busy={compare.phase === "loading"}
      />

      {compare.phase === "none" && usage?.usage && usage.usage.remaining < aspects.length && (
        <DailyLimit used={usage.usage.used} limit={usage.usage.limit} resetsAt={usage.usage.resets_at} question="Compare papers" what="Comparisons" onOpenPassage={setOpen} />
      )}

      {compare.phase === "failed" && compare.error && (
        <TurnFailure
          what="Comparisons"
          kind={compare.error.kind}
          fields={compare.error.fields}
          question="Compare papers"
          onRetry={() => void compare.start()}
          onOpenPassage={setOpen}
        />
      )}

      {pending && !running && (
        <div role="status" className="flex flex-col gap-3 rounded-2xl border border-amber/50 p-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-text">
            The last regeneration did not finish {pending.failed_aspects.map(labelOf).join(", ")}, so this comparison stays until it does.
          </p>
          <CostButton
            label="Finish the regeneration"
            cost={pending.retry_aspects.length}
            onClick={() => void compare.start({ retry_aspects: pending.retry_aspects })}
            primary={false}
          />
        </div>
      )}

      {showTable && (
        <>
          <CompareTable
            papers={papers}
            aspects={done && !running ? (done.aspects as ComparisonAspect[]) : aspects}
            saved={savedRows}
            parts={compare.parts}
            progress={compare.progress}
            retry={compare.retry}
            failedRows={compare.failedRows}
            running={running}
            retrying={compare.retrying}
            passages={passages}
            onOpen={setOpen}
            onRetryRow={stale ? undefined : (aspect) => void compare.start({ retry_aspects: [aspect] })}
          />
          {done && !running && (
            <p className="text-sm text-muted-foreground">
              {done.verified_cells} of {done.total_cells} cells verified. Passages were retrieved from each paper separately, so no
              paper crowds out another. Click any number to open the passage in the PDF.
            </p>
          )}
        </>
      )}

      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent className="border-line bg-panel">
          <DialogHeader>
            <DialogTitle className="font-heading text-text">Regenerate this comparison?</DialogTitle>
            <DialogDescription>
              It uses {aspects.length} request{aspects.length === 1 ? "" : "s"}
              {usage?.usage ? ` (${usage.usage.remaining} left today)` : ""}. The saved comparison stays until the new one is complete.
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
                void compare.start({ regenerate: true });
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
