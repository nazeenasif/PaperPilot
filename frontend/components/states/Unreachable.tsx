import { PlugZap, ServerCrash } from "lucide-react";

/** The API can't be reached, or it started but failed to load. Never shows server text. */
export function Unreachable({ failedToStart = false }: { failedToStart?: boolean }) {
  const Icon = failedToStart ? ServerCrash : PlugZap;
  return (
    <section role="alert" className="mx-auto flex max-w-xl flex-col items-center px-4 py-24 text-center">
      <span className="flex size-12 items-center justify-center rounded-xl bg-panel-2">
        <Icon aria-hidden className="size-6 text-amber" />
      </span>
      {failedToStart ? (
        <>
          <h2 className="mt-6 text-2xl font-semibold">PaperPilot couldn&apos;t start</h2>
          <p className="mt-3 text-muted-foreground">
            Loading the model or your library failed. The details are in{" "}
            <code className="font-mono text-text">data/library/api.log</code>. Fix the problem, then restart the server
            with:
          </p>
        </>
      ) : (
        <>
          <h2 className="mt-6 text-2xl font-semibold">Can&apos;t reach PaperPilot</h2>
          <p className="mt-3 text-muted-foreground">Start the server in a terminal in the project folder:</p>
        </>
      )}
      <code className="mt-4 rounded-lg border border-line bg-panel px-4 py-2 font-mono text-sm text-text">python -m api</code>
      <p className="mt-4 text-sm text-muted-foreground">This page reconnects by itself.</p>
    </section>
  );
}
