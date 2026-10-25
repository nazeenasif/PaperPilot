import { CitationChip } from "@/components/ask/CitationChip";
import { splitSegments, splitSentences } from "@/lib/sentences";
import type { NumberedPassage } from "@/lib/types";

/** Checked text with its [n] citations as chips that open the source viewer. A chip whose
 *  passage is not known yet (still streaming) shows its number without opening. */
export function CitedText({
  text,
  passages,
  onOpen,
}: {
  text: string;
  passages: Map<number, NumberedPassage>;
  onOpen: (passage: NumberedPassage) => void;
}) {
  return (
    <>
      {splitSentences(text).map((sentence, index) => (
        <span key={index}>
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
