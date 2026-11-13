import { DailyLimit } from "@/components/states/DailyLimit";
import { ModelBusy } from "@/components/states/ModelBusy";
import { ModelUnavailable } from "@/components/states/ModelUnavailable";
import { RateLimited } from "@/components/states/RateLimited";
import { StateButton, StateCard } from "@/components/states/StateCard";
import { GENERIC_FAILURE, GENERIC_FAILURES } from "@/lib/errorKinds";
import type { NumberedPassage } from "@/lib/types";

/** Only these typed fields are ever read from an error; nothing else from the network is shown. */
function field<T extends "string" | "number" | "boolean">(fields: Record<string, unknown>, name: string, type: T) {
  const value = fields[name];
  return (typeof value === type ? value : undefined) as
    | (T extends "string" ? string : T extends "number" ? number : boolean)
    | undefined;
}

/** A failed question as its designed state, chosen by error kind (FR-022). */
export function TurnFailure({
  kind,
  fields,
  question,
  model,
  dailyLimit,
  onRetry,
  onOpenPassage,
  what,
}: {
  /** What stops until the daily limit resets; answers by default. */
  what?: string;
  kind: string;
  fields: Record<string, unknown>;
  question: string;
  model?: string;
  dailyLimit?: number;
  onRetry: () => void;
  onOpenPassage?: (passage: NumberedPassage) => void;
}) {
  const resetsAt = field(fields, "resets_at", "string");
  const until = field(fields, "until", "string");

  if (kind === "daily_limit" && resetsAt) {
    return (
      <DailyLimit
        used={field(fields, "used", "number")}
        limit={field(fields, "limit", "number")}
        resetsAt={resetsAt}
        question={question}
        onOpenPassage={onOpenPassage}
        what={what}
      />
    );
  }
  if (kind === "rate_limited" && until) {
    return field(fields, "daily", "boolean") ? (
      <DailyLimit used={dailyLimit} limit={dailyLimit} resetsAt={until} question={question} onOpenPassage={onOpenPassage} />
    ) : (
      <RateLimited until={until} onRetry={onRetry} />
    );
  }
  if (kind === "model_busy") return <ModelBusy attempts={field(fields, "attempts", "number")} onRetry={onRetry} />;
  if (kind === "model_unavailable") return <ModelUnavailable reason={field(fields, "reason", "string")} model={model} />;

  const copy = GENERIC_FAILURES[kind] ?? GENERIC_FAILURE;
  return (
    <StateCard label="Something went wrong" alert>
      <p className="font-heading text-lg font-semibold text-text">{copy.message}</p>
      <p className="text-muted-foreground">{copy.next}</p>
      <StateButton onClick={onRetry}>Try again</StateButton>
    </StateCard>
  );
}
