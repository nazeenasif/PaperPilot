import type { ReactNode } from "react";

/** The frame shared by the designed states: a small mono label above the content (states.png). */
export function StateCard({
  label,
  tone = "plain",
  alert = false,
  children,
}: {
  label: string;
  tone?: "plain" | "amber";
  alert?: boolean;
  children: ReactNode;
}) {
  return (
    <section
      role={alert ? "alert" : undefined}
      aria-label={label}
      className={`space-y-4 rounded-2xl border bg-panel p-5 ${tone === "amber" ? "border-amber/50" : "border-line"}`}
    >
      <p className="font-mono text-xs tracking-[0.15em] text-muted-foreground uppercase">{label}</p>
      {children}
    </section>
  );
}

/** A secondary action button in a state. */
export function StateButton({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-full border border-line bg-panel-2 px-4 py-2 text-sm text-text transition-colors hover:border-teal/60"
    >
      {children}
    </button>
  );
}
