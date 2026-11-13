"use client";

import { ArrowRight } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

/** The composer's element id, so states can move focus to it ("Rephrase more specifically"). */
export const COMPOSER_ID = "ask-composer";

/** The question box: Enter sends, Shift+Enter adds a line; disabled while answering (FR-010).
 *  `blocked` disables sending and says why (e.g. no paper to search). `prefill` puts a question in
 *  the box (a new `key` each time) and focuses it, without sending. */
export function Composer({
  busy,
  blocked,
  prefill,
  onAsk,
}: {
  busy: boolean;
  blocked?: string;
  prefill?: { text: string; key: number };
  onAsk: (question: string) => void;
}) {
  const [text, setText] = useState("");
  const [hint, setHint] = useState<string | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!prefill) return;
    setText(prefill.text);
    setHint(null);
    const element = box.current;
    if (element) {
      element.focus();
      element.setSelectionRange(prefill.text.length, prefill.text.length);
    }
  }, [prefill]);

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (busy || blocked) return;
    const question = text.trim();
    if (!question) {
      setHint("Type a question first.");
      return;
    }
    setHint(null);
    setText("");
    onAsk(question);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form onSubmit={submit} className="w-full">
      <div className="flex items-end gap-2 rounded-2xl border border-teal/30 bg-panel p-2 focus-within:border-teal/70">
        <textarea
          ref={box}
          id={COMPOSER_ID}
          aria-label="Ask about your papers"
          aria-describedby={hint || blocked ? "composer-hint" : undefined}
          placeholder="Ask about the selected papers…"
          rows={1}
          value={text}
          disabled={busy}
          onChange={(event) => {
            setText(event.target.value);
            if (hint) setHint(null);
          }}
          onKeyDown={onKeyDown}
          className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-base text-text placeholder:text-muted-foreground focus:outline-none disabled:opacity-60"
        />
        <button
          type="submit"
          aria-label="Send question"
          disabled={busy || Boolean(blocked)}
          className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-teal text-ink transition-colors hover:bg-teal/85 disabled:opacity-50"
        >
          <ArrowRight aria-hidden className="size-5" />
        </button>
      </div>
      {(hint || blocked) && (
        <p id="composer-hint" role="status" className="mt-2 text-sm text-amber">
          {hint ?? blocked}
        </p>
      )}
    </form>
  );
}
