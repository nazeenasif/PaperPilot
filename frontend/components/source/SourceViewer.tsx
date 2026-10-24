"use client";

import { ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { HighlightOverlay } from "@/components/source/HighlightOverlay";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ApiError, apiGet, apiPost, apiUrl } from "@/lib/api";
import type { NumberedPassage, PassageView } from "@/lib/types";

const PdfPage = dynamic(() => import("@/components/source/PdfPage"), { ssr: false });

const DEFAULT_PAGE_WIDTH = 520;

type Load = { state: "loading" } | { state: "loaded"; view: PassageView } | { state: "failed"; kind: string };
type Reprocess = "idle" | "starting" | "started" | "failed";

/** The cited passage in its PDF page, highlighted (User Story 2, FR-012–FR-014). */
export function SourceViewer({
  citation,
  onClose,
  pageWidth: fixedWidth,
}: {
  citation: NumberedPassage;
  onClose: () => void;
  /** Rendered page width in pixels; by default fits the window (phone width, FR-029). */
  pageWidth?: number;
}) {
  const [measuredWidth] = useState(() =>
    typeof window === "undefined" ? DEFAULT_PAGE_WIDTH : Math.min(DEFAULT_PAGE_WIDTH, window.innerWidth - 40),
  );
  const pageWidth = fixedWidth ?? measuredWidth;
  // The chip that opened the viewer; Radix only restores focus to its own triggers (FR-030).
  const [opener] = useState(() => (typeof document === "undefined" ? null : (document.activeElement as HTMLElement | null)));
  useEffect(() => () => void setTimeout(() => opener?.focus(), 0), [opener]);
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [page, setPage] = useState(citation.page);
  const [reprocess, setReprocess] = useState<Reprocess>("idle");

  useEffect(() => {
    let cancelled = false;
    setLoad({ state: "loading" });
    setPage(citation.page);
    apiGet<PassageView>(`/api/passages/${encodeURIComponent(citation.passage_id)}`)
      .then((view) => !cancelled && setLoad({ state: "loaded", view }))
      .catch((error: unknown) => {
        if (!cancelled) setLoad({ state: "failed", kind: error instanceof ApiError ? error.kind : "internal" });
      });
    return () => {
      cancelled = true;
    };
  }, [citation.passage_id, citation.page]);

  const view = load.state === "loaded" ? load.view : null;
  const layout = view?.layout ?? null;
  const pageSize = layout?.pages.find((p) => p.number === page);
  const scale = pageSize ? pageWidth / pageSize.width : 0;
  const continuesOn = layout?.regions.find((r) => r.page > (view?.page ?? 0))?.page;

  async function startReprocess() {
    if (!view) return;
    setReprocess("starting");
    try {
      await apiPost(`/api/papers/${encodeURIComponent(view.paper_id)}/reprocess`, {});
      setReprocess("started");
    } catch {
      setReprocess("failed");
    }
  }

  return (
    <Sheet open onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full gap-3 overflow-y-auto p-5 sm:max-w-xl">
        <SheetHeader className="p-0 pr-8">
          <p className="font-mono text-xs tracking-wide text-amber">SOURCE {citation.number}</p>
          <SheetTitle className="font-heading text-lg leading-snug text-text">{citation.title}</SheetTitle>
          <SheetDescription className="flex flex-wrap items-center gap-x-3 text-muted-foreground">
            <span>
              {citation.section} · page {view?.page ?? citation.page}
              {view ? ` of ${view.page_count}` : ""}
            </span>
            <span className="rounded-md border border-line px-2 py-0.5 font-mono text-xs">score {citation.score.toFixed(3)}</span>
          </SheetDescription>
        </SheetHeader>

        {load.state === "loading" && <p className="text-sm text-muted-foreground">Loading the source…</p>}

        {load.state === "failed" && (
          <p role="alert" className="rounded-xl border border-amber/40 bg-panel px-4 py-3 text-text">
            {load.kind === "unknown_passage"
              ? "This passage is no longer in your library. Ask the question again to get current sources."
              : "The source couldn't be loaded. Please try again."}
          </p>
        )}

        {view && view.has_pdf && (
          <>
            <div className="relative self-center overflow-hidden rounded-lg bg-page" style={{ width: pageWidth }}>
              <PdfPage url={apiUrl(`/api/papers/${encodeURIComponent(view.paper_id)}/pdf`)} page={page} width={pageWidth} />
              {layout && scale > 0 && <HighlightOverlay regions={layout.regions} page={page} scale={scale} />}
            </div>
            <div className="flex items-center justify-between gap-2">
              <button
                type="button"
                aria-label="Previous page"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="flex size-9 items-center justify-center rounded-lg border border-line text-text disabled:opacity-40"
              >
                <ChevronLeft aria-hidden className="size-4" />
              </button>
              <span className="font-mono text-xs text-muted-foreground">
                page {page} of {view.page_count}
              </span>
              <button
                type="button"
                aria-label="Next page"
                disabled={page >= view.page_count}
                onClick={() => setPage((p) => Math.min(view.page_count, p + 1))}
                className="flex size-9 items-center justify-center rounded-lg border border-line text-text disabled:opacity-40"
              >
                <ChevronRight aria-hidden className="size-4" />
              </button>
            </div>
            {layout && continuesOn && page === view.page && (
              <p className="text-sm text-muted-foreground">The passage continues on page {continuesOn}.</p>
            )}
          </>
        )}

        {view && !layout && (
          <div className="space-y-3">
            <p className="text-sm text-amber">
              {view.layout_reason === "no_pdf"
                ? "The PDF of this paper isn't stored yet. Add the paper's file again on the Library screen to see it here."
                : "The exact location could not be marked on the page. This is the passage the model read:"}
            </p>
            <blockquote className="rounded-lg bg-page px-4 py-3 font-serif text-sm leading-relaxed text-passage-text">
              {view.text}
            </blockquote>
            {view.can_reprocess && reprocess !== "started" && (
              <button
                type="button"
                onClick={startReprocess}
                disabled={reprocess === "starting"}
                className="rounded-lg border border-teal/60 px-3 py-2 text-sm text-teal hover:bg-teal/10 disabled:opacity-50"
              >
                Re-process paper for exact highlights
              </button>
            )}
            {reprocess === "started" && (
              <p role="status" className="text-sm text-teal">
                Re-processing started. Exact highlights appear once it finishes.
              </p>
            )}
            {reprocess === "failed" && (
              <p role="alert" className="text-sm text-amber">
                Re-processing couldn&apos;t start. Please try again.
              </p>
            )}
          </div>
        )}

        {view?.has_pdf && (
          <div className="mt-auto flex flex-wrap items-center gap-3">
            <a
              href={apiUrl(`/api/papers/${encodeURIComponent(view.paper_id)}/pdf#page=${view.page}`)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-panel px-3 py-2 text-sm text-text hover:border-teal/60"
            >
              Open full PDF <ExternalLink aria-hidden className="size-4" />
            </a>
            {layout && <p className="text-sm text-muted-foreground">Highlighted text is exactly what the model read.</p>}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
