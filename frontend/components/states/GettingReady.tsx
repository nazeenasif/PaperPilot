import { LoaderCircle } from "lucide-react";

/** Shown while the server loads the embedding model and opens the library (FR-003). */
export function GettingReady() {
  return (
    <section role="status" aria-live="polite" className="mx-auto flex max-w-xl flex-col items-center px-4 py-24 text-center">
      <LoaderCircle aria-hidden className="size-8 text-teal motion-safe:animate-spin" />
      <h2 className="mt-6 text-2xl font-semibold">Getting ready</h2>
      <p className="mt-3 text-muted-foreground">
        PaperPilot is loading its embedding model and your library. The first start takes about half a minute.
      </p>
    </section>
  );
}
