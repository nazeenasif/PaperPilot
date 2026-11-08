import { LoaderCircle, TriangleAlert } from "lucide-react";

import { CompareCell } from "@/components/compare/CompareCell";
import { ASPECTS } from "@/components/compare/CompareForm";
import { Busy } from "@/components/states/Busy";
import { progressText } from "@/components/summary/SectionCard";
import { CostButton } from "@/components/summary/CostButton";
import { partProblem } from "@/lib/errorKinds";
import type { Comparison, ComparisonAspect, ComparisonRow, NumberedPassage, Part, RetryWaitEvent } from "@/lib/types";
import type { PartProgress } from "@/lib/useSummary";

const label = (aspect: string) => ASPECTS.find((a) => a.key === aspect)?.label ?? aspect;

/** One column per paper, one row per aspect. Scrolls inside its own container at phone width (FR-009). */
export function CompareTable({
  papers,
  aspects,
  saved,
  parts,
  progress,
  retry,
  failedRows,
  running,
  retrying,
  passages,
  onOpen,
  onRetryRow,
}: {
  papers: Comparison["papers"];
  aspects: ComparisonAspect[];
  /** The saved rows, by aspect. */
  saved: Map<string, ComparisonRow>;
  parts: Record<string, Part>;
  progress: Record<string, PartProgress>;
  retry: Record<string, { event: RetryWaitEvent; since: number }>;
  failedRows: Record<string, string>;
  running: boolean;
  retrying: string[] | null;
  passages: Map<number, NumberedPassage>;
  onOpen: (passage: NumberedPassage) => void;
  /** Absent on an earlier comparison, which only a full regeneration replaces. */
  onRetryRow?: (aspect: string) => void;
}) {
  return (
    <div tabIndex={0} role="region" aria-label="Comparison table" className="overflow-x-auto rounded-2xl border border-line bg-panel">
      <table className="w-full min-w-[40rem] border-collapse text-left align-top">
        <thead>
          <tr className="border-b border-line">
            <td className="w-32 p-4" />
            {papers.map((paper) => (
              <th key={paper.paper_id} scope="col" className="p-4 align-top font-heading font-semibold text-text">
                {paper.title}
                {paper.arxiv_id && <span className="block font-mono text-xs font-normal text-muted-foreground">arXiv {paper.arxiv_id}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {aspects.map((aspect) => {
            const live = running && (retrying === null || retrying.includes(aspect));
            const row = live ? undefined : saved.get(aspect);
            const reason = live ? failedRows[aspect] : row?.state !== "ok" ? row?.reason : undefined;
            const state = live ? (failedRows[aspect] ? "failed" : "ok") : row?.state;
            const wait = live ? retry[aspect] : undefined;
            const step = live ? progress[aspect] : undefined;
            const started = papers.some((p) => parts[`${aspect}:${p.paper_id}`]);
            return (
              <tr key={aspect} className="border-b border-line last:border-b-0">
                <th scope="row" className="p-4 align-top font-medium text-teal">
                  {label(aspect)}
                </th>
                {state === "failed" || state === "not_started" ? (
                  <td colSpan={papers.length} className="p-4 align-top">
                    <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <p className="flex gap-2 text-sm text-amber">
                        <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
                        <span>
                          {state === "failed" && reason === "malformed"
                            ? "This row couldn't be read"
                            : partProblem(state, reason ?? null, row?.until ?? null)}
                        </span>
                      </p>
                      {onRetryRow && !running && (
                        <CostButton label="Retry this row" cost={1} onClick={() => onRetryRow(aspect)} primary={false} />
                      )}
                    </div>
                  </td>
                ) : live && !started ? (
                  <td colSpan={papers.length} className="p-4 align-top">
                    {wait ? (
                      <Busy retry={wait.event} since={wait.since} />
                    ) : (
                      <p role="status" className="flex items-center gap-2 font-mono text-sm text-teal">
                        {step && <LoaderCircle aria-hidden className="size-4 motion-safe:animate-spin" />}
                        {progressText(label(aspect), step)}
                      </p>
                    )}
                  </td>
                ) : (
                  papers.map((paper) => {
                    const name = `${aspect}:${paper.paper_id}`;
                    const cell = live ? parts[name] : row?.cells.find((c) => c.part === name);
                    return (
                      <td key={paper.paper_id} className="p-4 align-top">
                        <CompareCell part={cell} passages={passages} onOpen={onOpen} />
                      </td>
                    );
                  })
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
