"use client";

import { ArrowUpRight, FileSearch, LibraryBig, MessageSquareText, Quote, Sparkles } from "lucide-react";
import Link from "next/link";

import type { PaperCard } from "@/lib/types";

/** A paper's name for a question: the title before its colon, or before its first "for", "via"
 *  or "with" ("LoRA", "Retrieval-Augmented Generation"); short titles are kept whole. */
export function shortTitle(title: string): string {
  const head = title.split(":")[0]!.trim();
  const cut = head.search(/\s+(?:for|via|with)\s+/i);
  return cut > 0 ? head.slice(0, cut) : head;
}

const KINDS = [
  (t: string) => `What problem does ${t} set out to solve?`,
  (t: string) => `How does the method in ${t} work?`,
  (t: string) => `What are the main results reported in ${t}?`,
];

/** Up to four starter questions from the selected papers: one of a different kind about each of
 *  the first three, and one across the first two; three kinds about a paper chosen alone. */
export function suggestions(papers: PaperCard[]): string[] {
  const names = papers.map((p) => shortTitle(p.title));
  if (names.length === 0) return [];
  if (names.length === 1) return KINDS.map((kind) => kind(names[0]!));
  const each = names.slice(0, 3).map((name, i) => KINDS[i]!(name));
  return [...each, `How do ${names[0]} and ${names[1]} differ in their approach?`];
}

const STEPS = [
  { icon: MessageSquareText, title: "Ask in plain words", text: "Type a question about the selected papers, or start from a suggestion." },
  { icon: Quote, title: "Read a cited answer", text: "Each sentence cites its passage, checked before you see it." },
  { icon: FileSearch, title: "Open the exact passage", text: "Click a number to see that passage highlighted in the PDF." },
];

/** The Ask screen before the first question: what it does, starter questions from the selected
 *  papers (they fill the box; nothing is sent until the reader does), and how it works. */
export function AskWelcome({
  papers,
  libraryEmpty,
  onPick,
}: {
  /** The selected papers; null while the library is loading. */
  papers: PaperCard[] | null;
  libraryEmpty: boolean;
  onPick: (question: string) => void;
}) {
  const starters = papers ? suggestions(papers) : [];
  const count = papers?.length ?? 0;

  return (
    <section
      aria-labelledby="ask-welcome-title"
      className="relative flex flex-1 flex-col justify-center gap-6 py-2 duration-500 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-2"
    >
      <div aria-hidden className="pointer-events-none absolute -top-10 left-1/2 -z-10 size-80 -translate-x-1/2 rounded-full bg-teal/10 blur-3xl" />

      <div className="space-y-3">
        <p className="font-mono text-xs tracking-[0.2em] text-teal">ASK</p>
        <h2 id="ask-welcome-title" className="font-heading text-3xl font-semibold tracking-tight text-text sm:text-5xl">
          Ask your papers anything
        </h2>
        {papers && !libraryEmpty && (
          <p className="max-w-2xl text-base text-muted-foreground">
            Answers come only from the {count} selected paper{count === 1 ? "" : "s"}, and every sentence cites the passage it
            came from.
          </p>
        )}
      </div>

      {libraryEmpty && (
        <div className="flex flex-col gap-4 rounded-2xl border border-line bg-panel p-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <LibraryBig aria-hidden className="mt-0.5 size-5 shrink-0 text-teal" />
            <p className="text-text">Your library is empty. Add a research paper as a PDF, then ask about it here.</p>
          </div>
          <Link
            href="/library"
            className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-teal px-4 py-2.5 font-medium text-ink hover:bg-teal/85"
          >
            Add a paper <ArrowUpRight aria-hidden className="size-4" />
          </Link>
        </div>
      )}

      {starters.length > 0 && (
        <div className="space-y-3">
          <p className="font-mono text-xs tracking-[0.2em] text-muted-foreground">TRY ONE OF THESE</p>
          <ul className="grid gap-3 sm:grid-cols-2">
            {starters.map((question) => (
              <li key={question}>
                <button
                  type="button"
                  aria-label={`Use this question: ${question}`}
                  onClick={() => onPick(question)}
                  className="group flex h-full w-full items-start gap-3 rounded-2xl border border-line bg-panel p-4 text-left text-text transition-colors hover:border-teal/60 hover:bg-panel-2 focus-visible:border-teal focus-visible:outline-none"
                >
                  <Sparkles aria-hidden className="mt-0.5 size-4 shrink-0 text-teal transition-transform group-hover:scale-110" />
                  <span className="leading-snug">{question}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <ol aria-label="How it works" className="grid gap-3 sm:grid-cols-3">
        {STEPS.map(({ icon: Icon, title, text }, i) => (
          <li key={title} className="flex items-center gap-3 rounded-2xl border border-line/70 p-3 sm:block sm:space-y-2 sm:p-4">
            <div className="flex items-center gap-2">
              <span className="flex size-7 items-center justify-center rounded-full border border-teal/50">
                <Icon aria-hidden className="size-3.5 text-teal" />
              </span>
              <span className="font-mono text-xs text-muted-foreground">{i + 1}</span>
            </div>
            <p className="font-medium text-text">{title}</p>
            <p className="hidden text-sm text-muted-foreground sm:block">{text}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
