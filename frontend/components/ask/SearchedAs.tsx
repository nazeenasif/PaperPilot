import type { Answer } from "@/lib/types";

/** What a follow-up was actually searched as (US4 scenarios 3 and 4). */
export function SearchedAs({ answer }: { answer: Answer }) {
  if (answer.rewrite_applied) {
    return <p className="font-mono text-xs text-muted-foreground">{`Searched as "${answer.standalone_question}"`}</p>;
  }
  if (answer.rewrite_fallback_reason) {
    return <p className="font-mono text-xs text-muted-foreground">Searched as typed</p>;
  }
  return null;
}
