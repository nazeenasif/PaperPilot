"use client";

import { useUsage } from "@/components/app/UsageMeter";

/** A button that starts model requests, with its cost and today's remaining requests beneath
 *  it ("uses 6 requests · 41 left today", FR-021). */
export function CostButton({
  label,
  cost,
  costNote,
  onClick,
  disabled = false,
  primary = true,
}: {
  label: string;
  cost: number;
  /** In place of "uses N requests", e.g. "uses 5 requests, 1 per aspect". */
  costNote?: string;
  onClick: () => void;
  disabled?: boolean;
  primary?: boolean;
}) {
  const usage = useUsage()?.usage;
  const left = usage ? ` · ${usage.remaining} left today` : "";
  return (
    <div className="flex flex-col items-start gap-1.5 sm:items-end">
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        className={`rounded-xl px-5 py-3 font-medium transition-colors disabled:opacity-50 ${
          primary ? "bg-teal text-ink hover:bg-teal/85" : "border border-line bg-panel text-text hover:border-teal/60"
        }`}
      >
        {label}
      </button>
      <p className="font-mono text-xs text-muted-foreground">
        {costNote ?? `uses ${cost} request${cost === 1 ? "" : "s"}`}
        {left}
      </p>
    </div>
  );
}
