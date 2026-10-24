"use client";

import { Navigation2 } from "lucide-react";

import { useStatus } from "@/components/app/StatusGate";

/** A readable model name: no provider prefix, no ":free", no mixture-of-experts size suffix. */
export function modelLabel(model: string, isFree: boolean): string {
  const name = (model.split("/").pop() ?? model).replace(/:free$/, "").replace(/-\d+b-a\d+b$/i, "");
  return isFree ? `${name} · free` : name;
}

/** Top bar: name, tagline and the configured model (FR-024). */
export function Header() {
  const connection = useStatus();
  const status = connection.kind === "status" ? connection.status : null;

  return (
    <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3 sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full border border-teal/60">
          <Navigation2 aria-hidden className="size-4 rotate-45 text-teal" />
        </span>
        <span className="font-heading text-lg font-semibold">PaperPilot</span>
        <span className="hidden rounded-full border border-line px-2 py-0.5 font-mono text-xs text-muted-foreground sm:inline">
          grounded answers
        </span>
      </div>
      {status && (
        <span className="truncate rounded-lg border border-line bg-panel px-3 py-1 font-mono text-xs text-muted-foreground">
          {modelLabel(status.model, status.model_is_free)}
        </span>
      )}
    </header>
  );
}
