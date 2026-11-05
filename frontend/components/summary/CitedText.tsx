import { CitationChip } from "@/components/ask/CitationChip";
import { splitSegments, splitSentences } from "@/lib/sentences";
import type { NumberedPassage } from "@/lib/types";

/** Checked text with its [n] citations as chips that open the source viewer. A chip whose
 *  passage is not known yet (still streaming) shows its number without opening. Sentences listed
 *  in `uncited` are underlined, as in an Ask answer. */
export function CitedText({
  text,
  passages,
  onOpen,
  uncited = [],
}: {
  text: string;
  passages: Map<number, NumberedPassage>;
  onOpen: (passage: NumberedPassage) => void;
  uncited?: string[];
}) {
  const flagged = new Set(uncited.map((s) => s.trim()));
  return (
    <>
      {splitSentences(text).map((sentence, index) => (
        <span
          key={index}
          {...(flagged.has(sentence.trim()) && {
            "data-uncited": "",
            title: "This sentence has no citation",
            className: "underline decoration-amber/70 decoration-dotted underline-offset-4",
          })}
        >
          {splitSegments(sentence).map((segment, i) =>
            segment.kind === "text" ? (
              <span key={i}>{segment.text}</span>
            ) : (
              <span key={i}>
                {segment.numbers.map((number) => (
                  <CitationChip key={number} number={number} passage={passages.get(number)} onOpen={onOpen} />
                ))}
              </span>
            ),
          )}{" "}
        </span>
      ))}
    </>
  );
}
