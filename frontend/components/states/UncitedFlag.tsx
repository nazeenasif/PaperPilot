/** A gentle note under an answer with sentences that carry no citation; it doesn't block the
 *  answer (US5 scenario 7). The sentences themselves are underlined by AnswerView. */
export function UncitedFlag({ count }: { count: number }) {
  if (count === 0) return null;
  return (
    <p className="w-fit rounded-full border border-line bg-panel px-3 py-1 text-sm text-text">
      {count} sentence{count === 1 ? " has" : "s have"} no citation
    </p>
  );
}
