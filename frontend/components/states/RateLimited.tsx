import { StateButton, StateCard } from "@/components/states/StateCard";
import { localTime } from "@/lib/errorKinds";

/** The provider asked for a wait longer than a minute, not for the day (FR-023a). */
export function RateLimited({ until, onRetry }: { until: string; onRetry: () => void }) {
  return (
    <StateCard label="Rate limited" alert>
      <p className="font-heading text-lg font-semibold text-text">Try again at {localTime(until)}</p>
      <p className="text-muted-foreground">
        The free model asked PaperPilot to wait, so nothing more was sent. Your question is kept.
      </p>
      <StateButton onClick={onRetry}>Try again</StateButton>
    </StateCard>
  );
}
