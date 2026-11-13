/** A citation whose passage has since left the library (deleted or re-processed paper). */
export function PassageGone() {
  return (
    <div role="alert" className="space-y-1 rounded-xl border border-amber/40 bg-panel px-4 py-3">
      <p className="text-text">This passage is no longer in your library</p>
      <p className="text-sm text-muted-foreground">
        Its paper was deleted or re-processed. Ask the question again to get current sources.
      </p>
    </div>
  );
}
