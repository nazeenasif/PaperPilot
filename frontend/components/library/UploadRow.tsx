import { Check, Circle, LoaderCircle, TriangleAlert } from "lucide-react";

import { uploadFailure } from "@/lib/errorKinds";
import type { JobPhase, UploadJob } from "@/lib/types";

const STEPS: { phase: JobPhase; label: string }[] = [
  { phase: "parsing", label: "Parsing" },
  { phase: "chunking", label: "Chunking" },
  { phase: "embedding", label: "Embedding" },
  { phase: "ready", label: "Ready" },
];
const ORDER: JobPhase[] = ["queued", ...STEPS.map((step) => step.phase)];

/** The status line at the right of a row. */
function statusText(job: UploadJob): string {
  switch (job.phase) {
    case "queued":
      return "Waiting in line";
    case "parsing":
      return "Reading the PDF";
    case "chunking":
      return "Splitting into passages";
    case "embedding":
      return `Embedding passages · ${job.percent ?? 0}%`;
    case "mapping":
      return "Mapping highlights";
    case "failed":
      return "Not added";
    case "ready":
      switch (job.outcome) {
        case "already_present":
          return "Already in your library";
        case "pdf_attached":
          return job.highlights === "mismatch" ? "PDF attached — exact highlights unavailable" : "PDF attached";
        case "reprocessed":
          return "Re-processed";
        default:
          return "Added to your library";
      }
  }
}

function stepState(job: UploadJob, phase: JobPhase): "done" | "active" | "pending" {
  if (job.phase === "ready") return "done";
  const current = ORDER.indexOf(job.phase);
  const index = ORDER.indexOf(phase);
  if (index < current) return "done";
  return index === current ? "active" : "pending";
}

/** One dropped file (or re-process) and its progress (FR-017, FR-018). */
export function UploadRow({ job }: { job: UploadJob }) {
  const failed = job.phase === "failed";
  const attach = job.phase === "mapping" || job.outcome === "pdf_attached";
  const showSteps = !failed && !attach && job.outcome !== "already_present";
  const percent = job.phase === "ready" ? 100 : job.phase === "embedding" ? (job.percent ?? 0) : 0;
  const working = !failed && job.phase !== "ready";
  const failure = failed ? uploadFailure(job.error) : null;

  return (
    <li className="space-y-3 rounded-2xl border border-line bg-panel px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <span className="min-w-0 truncate font-medium text-text">{job.file_name}</span>
        <span
          role="status"
          className={`font-mono text-xs ${failed ? "text-amber" : working ? "text-amber" : "text-teal"}`}
        >
          {statusText(job)}
        </span>
      </div>
      {showSteps && (
        <>
          <div
            role="progressbar"
            aria-label={`Progress for ${job.file_name}`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
            className="h-1.5 overflow-hidden rounded-full bg-panel-2"
          >
            <div className="h-full rounded-full bg-teal transition-[width] duration-300" style={{ width: `${percent}%` }} />
          </div>
          <ol className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
            {STEPS.map(({ phase, label }) => {
              const state = stepState(job, phase);
              const Icon = state === "done" ? Check : state === "active" ? LoaderCircle : Circle;
              return (
                <li
                  key={phase}
                  className={`flex items-center gap-1.5 ${
                    state === "done" ? "text-teal" : state === "active" ? "text-amber" : "text-muted-foreground"
                  }`}
                >
                  <Icon aria-hidden className={`size-3.5 ${state === "active" ? "motion-safe:animate-spin" : ""}`} />
                  <span data-state={state}>{label}</span>
                </li>
              );
            })}
          </ol>
        </>
      )}
      {job.outcome === "already_present" && job.paper_id && (
        <a href={`#paper-${job.paper_id}`} className="text-sm text-teal underline-offset-4 hover:underline">
          View the paper
        </a>
      )}
      {failure && (
        <div className="flex gap-2 text-sm">
          <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-amber" />
          <p className="text-text">
            <span>{failure.message}</span> <span className="text-muted-foreground">{failure.next}</span>
          </p>
        </div>
      )}
    </li>
  );
}
