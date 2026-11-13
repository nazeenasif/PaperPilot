"use client";

import { Upload } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";

/** Drop PDFs here or choose them, several at a time (FR-016). Every file is sent: the server
 *  rejects what isn't a usable PDF, and each rejection gets its own row. */
export function DropZone({ onFiles }: { onFiles: (files: File[]) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  function onDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    setOver(false);
    const files = Array.from(event.dataTransfer?.files ?? []);
    if (files.length > 0) onFiles(files);
  }

  return (
    <section
      aria-label="Add papers"
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      className={`flex flex-col gap-4 rounded-2xl border border-dashed p-5 transition-colors sm:flex-row sm:items-center sm:p-7 ${
        over ? "border-teal bg-teal/5" : "border-teal/40 bg-panel/40"
      }`}
    >
      <span className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-panel-2 text-teal">
        <Upload aria-hidden className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-heading text-lg font-semibold text-text">Drop research papers here</p>
        <p className="text-sm text-muted-foreground">Text-based PDFs up to 25 MB · duplicates are detected automatically</p>
      </div>
      <input
        ref={input}
        type="file"
        multiple
        accept="application/pdf,.pdf"
        aria-label="Choose PDF files"
        className="sr-only"
        tabIndex={-1}
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          event.target.value = "";
          if (files.length > 0) onFiles(files);
        }}
      />
      <button
        type="button"
        onClick={() => input.current?.click()}
        className="rounded-xl bg-teal px-5 py-3 font-medium text-ink transition-colors hover:bg-teal/85"
      >
        Choose files
      </button>
    </section>
  );
}
