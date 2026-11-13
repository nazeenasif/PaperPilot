import { StateCard } from "@/components/states/StateCard";
import { MODEL_UNAVAILABLE_DEFAULT, MODEL_UNAVAILABLE_HINTS } from "@/lib/errorKinds";

/** The configured model can't be used as set up: which model, and which setting to change.
 *  The API key itself is never shown (FR-022). */
export function ModelUnavailable({ reason, model }: { reason?: string; model?: string }) {
  return (
    <StateCard label="Model unavailable" alert>
      <p className="font-heading text-lg font-semibold text-text">PaperPilot can&apos;t use the configured model</p>
      <p className="text-muted-foreground">
        Model: <span className="font-mono text-text">{model ?? "the model set in LLM_MODEL"}</span>
      </p>
      <p className="text-text">{(reason && MODEL_UNAVAILABLE_HINTS[reason]) || MODEL_UNAVAILABLE_DEFAULT}</p>
    </StateCard>
  );
}
