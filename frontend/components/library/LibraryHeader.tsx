function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

/** "5 papers, 223 searchable passages", and that embeddings stay on this machine (FR-019). */
export function LibraryHeader({ papers, passages }: { papers: number; passages: number }) {
  return (
    <header className="space-y-2">
      <p className="font-mono text-xs tracking-[0.2em] text-teal">YOUR LIBRARY</p>
      <h1 className="font-heading text-3xl font-semibold tracking-tight text-text sm:text-5xl">
        {plural(papers, "paper")}, {plural(passages, "searchable passage")}
      </h1>
      <p className="font-mono text-xs text-muted-foreground sm:text-sm">Embeddings run on this machine · nothing leaves it</p>
    </header>
  );
}
