import { StateButton, StateCard } from "@/components/states/StateCard";

/** Every retry failed: the question is kept and can be asked again (FR-022, US5 scenario 4). */
export function ModelBusy({ attempts, onRetry }: { attempts?: number; onRetry: () => void }) {
  return (
    <StateCard label="Model busy" alert>
      <p className="font-heading text-lg font-semibold text-text">The free model is still busy</p>
      <p className="text-muted-foreground">
        PaperPilot tried {attempts ?? "several"} times without an answer. Your question is kept — try again in a minute.
      </p>
      <StateButton onClick={onRetry}>Try again</StateButton>
    </StateCard>
  );
}
