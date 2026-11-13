"use client";

import { Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError, apiDelete, apiPost } from "@/lib/api";
import type { PaperCard as Paper } from "@/lib/types";

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex flex-col">
      <span className="font-heading text-2xl font-semibold text-text">{value}</span>
      <span className="text-sm text-muted-foreground">{label}</span>
    </div>
  );
}

/** One paper: title, counts, arXiv ID, "Ask this paper" and delete (FR-019–FR-021). */
export function PaperCard({
  paper,
  onDeleted,
  onReprocessing,
}: {
  paper: Paper;
  onDeleted: (paperId: string) => void;
  onReprocessing?: (job: { job_id: string; file_name: string }) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [working, setWorking] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  async function remove() {
    setWorking(true);
    try {
      await apiDelete(`/api/papers/${paper.paper_id}`);
      setConfirming(false);
      onDeleted(paper.paper_id);
    } catch {
      setNote("Couldn't delete this paper. Try again in a moment.");
    } finally {
      setWorking(false);
    }
  }

  async function reprocess() {
    setNote(null);
    try {
      const job = await apiPost<{ job_id: string; file_name: string }>(`/api/papers/${paper.paper_id}/reprocess`, undefined);
      onReprocessing?.(job);
      setNote("Re-processing — follow it in the list above.");
    } catch (error) {
      setNote(
        error instanceof ApiError && error.kind === "busy_job"
          ? "This paper is already being processed."
          : "Couldn't start re-processing. Try again in a moment.",
      );
    }
  }

  return (
    <article id={`paper-${paper.paper_id}`} className="flex scroll-mt-24 flex-col gap-4 rounded-2xl border border-line bg-panel p-5">
      <div className="flex items-start justify-between gap-3">
        <span aria-hidden className="flex h-12 w-10 flex-col justify-center gap-1 rounded-sm bg-page px-1.5">
          <span className="h-0.5 rounded bg-passage-text/30" />
          <span className="h-0.5 rounded bg-passage-text/30" />
          <span className="h-0.5 w-2/3 rounded bg-passage-text/30" />
        </span>
        {paper.arxiv_id && <span className="font-mono text-xs text-muted-foreground">arXiv {paper.arxiv_id}</span>}
      </div>
      <h2 className="font-heading text-lg leading-snug font-semibold text-text">{paper.title}</h2>
      <div className="grid grid-cols-3 gap-2">
        <Stat value={paper.passage_count} label="passages" />
        <Stat value={paper.section_count} label="sections" />
        <Stat value={paper.page_count} label="pages" />
      </div>
      <p className="font-mono text-xs text-muted-foreground">
        {paper.text_passages} text · {paper.table_passages} table
      </p>
      {paper.highlights === "mismatch" && paper.has_pdf && (
        <button
          type="button"
          onClick={reprocess}
          className="self-start text-sm text-amber underline-offset-4 hover:underline"
        >
          Re-process for exact highlights
        </button>
      )}
      {note && (
        <p role="status" className="text-sm text-muted-foreground">
          {note}
        </p>
      )}
      <div className="mt-auto flex gap-2">
        <Link
          href={`/?paper=${paper.paper_id}`}
          className="flex-1 rounded-xl bg-teal px-4 py-2.5 text-center font-medium text-ink transition-colors hover:bg-teal/85"
        >
          Ask this paper
        </Link>
        <Link
          href={`/summarize/${paper.paper_id}`}
          className="rounded-xl border border-line px-4 py-2.5 text-center text-text transition-colors hover:border-teal/60"
        >
          Summarize
        </Link>
        <button
          type="button"
          aria-label={`Delete ${paper.title}`}
          onClick={() => setConfirming(true)}
          className="flex size-11 items-center justify-center rounded-xl border border-line text-muted-foreground transition-colors hover:border-amber/60 hover:text-amber"
        >
          <Trash2 aria-hidden className="size-4" />
        </button>
      </div>
      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent className="border-line bg-panel">
          <DialogHeader>
            <DialogTitle className="font-heading text-text">Delete this paper?</DialogTitle>
            <DialogDescription>
              &ldquo;{paper.title}&rdquo;, its {paper.passage_count} passages and its PDF will be removed from your
              library. This can&apos;t be undone.
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
              onClick={remove}
              disabled={working}
              className="rounded-xl bg-amber px-4 py-2.5 font-medium text-ink hover:bg-amber/85 disabled:opacity-60"
            >
              Delete paper
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </article>
  );
}
