import { Check } from "lucide-react";

/** Shown only when every citation was checked against the passages the model was given (FR-005). */
export function VerifiedBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-teal/50 px-3 py-1 text-sm text-teal">
      <Check aria-hidden className="size-4" />
      All citations verified
    </span>
  );
}
