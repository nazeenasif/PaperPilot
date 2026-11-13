"use client";

import { SlidersHorizontal } from "lucide-react";
import { useState } from "react";

import { useStatus } from "@/components/app/StatusGate";
import { useUsage } from "@/components/app/UsageMeter";
import { COMPOSER_ID, Composer } from "@/components/ask/Composer";
import { Conversation } from "@/components/ask/Conversation";
import { ScopePanel } from "@/components/library/ScopePanel";
import { SourceViewer } from "@/components/source/SourceViewer";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import type { NumberedPassage } from "@/lib/types";
import { useAsk } from "@/lib/useAsk";
import { useScope } from "@/lib/useScope";

/** The Ask screen: the paper scope, the conversation, the composer and the source viewer
 *  opened from citation chips (User Stories 1, 2 and 4). */
export function AskScreen() {
  const usage = useUsage();
  const scope = useScope();
  const { turns, busy, ask, reset } = useAsk({
    // The meter follows each answer's figure; after a failure it asks the server (FR-024).
    onAnswer: (answer) => answer.usage && usage?.report(answer.usage),
    onFailure: () => void usage?.refresh(),
  });
  const [openPassage, setOpenPassage] = useState<NumberedPassage | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const connection = useStatus();
  const status = connection.kind === "status" ? connection.status : null;
  const rephrase = () => document.getElementById(COMPOSER_ID)?.focus();
  const askInScope = (question: string) => void ask(question, { paperIds: scope.paperIds });
  const noPapers = scope.papers !== null && scope.papers.length === 0;
  const scopeLabel = scope.papers ? `${scope.selected.length} of ${scope.papers.length}` : null;

  return (
    <div className="mx-auto flex w-full max-w-6xl gap-8 px-4 sm:px-6">
      <aside className="sticky top-4 hidden max-h-[calc(100vh-6rem)] w-72 shrink-0 self-start overflow-y-auto pt-8 lg:block">
        <ScopePanel scope={scope} />
      </aside>
      <main className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-3xl min-w-0 flex-col pt-8 pb-6">
        <h1 className="sr-only">Ask your papers</h1>
        <div className="mb-6 flex items-center justify-between gap-3">
          {scopeLabel && (
            <button
              type="button"
              aria-label={`Choose papers (${scopeLabel} selected)`}
              onClick={() => setSheetOpen(true)}
              className="flex items-center gap-2 rounded-lg border border-line px-3 py-1.5 font-mono text-xs text-muted-foreground hover:text-text lg:hidden"
            >
              <SlidersHorizontal aria-hidden className="size-3.5" />
              Papers · {scopeLabel}
            </button>
          )}
          {turns.length > 0 && (
            <button
              type="button"
              onClick={reset}
              disabled={busy}
              className="ml-auto rounded-lg border border-line px-3 py-1.5 text-sm text-muted-foreground hover:text-text disabled:opacity-50"
            >
              New conversation
            </button>
          )}
        </div>
        <Conversation
          turns={turns}
          canSearchAll={!scope.isAll}
          model={status?.model}
          dailyLimit={status?.daily_limit}
          onAsk={askInScope}
          onSearchAll={(question) => {
            scope.selectAll();
            void ask(question);
          }}
          onRephrase={rephrase}
          onOpenPassage={setOpenPassage}
        />
        <div className="sticky bottom-0 mt-8 bg-background pt-2">
          <Composer busy={busy} blocked={noPapers ? "Add a paper in the Library first." : undefined} onAsk={askInScope} />
          <p className="mt-2 text-sm text-muted-foreground">
            Every answer cites the passage it came from. Click a number to see it in the paper.
          </p>
        </div>
        {openPassage && <SourceViewer citation={openPassage} onClose={() => setOpenPassage(null)} />}
      </main>
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent side="left" className="w-[85vw] max-w-sm overflow-y-auto p-5">
          <SheetHeader className="p-0">
            <SheetTitle className="font-heading text-text">Papers to search</SheetTitle>
            <SheetDescription>Questions search only the selected papers.</SheetDescription>
          </SheetHeader>
          <ScopePanel scope={scope} />
        </SheetContent>
      </Sheet>
    </div>
  );
}
