"use client";

import { motion, useReducedMotion } from "motion/react";

import { CitationChip } from "@/components/ask/CitationChip";
import { VerifiedBadge } from "@/components/ask/VerifiedBadge";
import { UncitedFlag } from "@/components/states/UncitedFlag";
import { revealPlan } from "@/lib/reveal";
import { splitSegments, splitSentences } from "@/lib/sentences";
import type { Answer, NumberedPassage } from "@/lib/types";

/** The checked answer: sentences fade in, then chips, then the badge, in under 500 ms (FR-011). */
export function AnswerView({ answer, onOpenCitation }: { answer: Answer; onOpenCitation: (p: NumberedPassage) => void }) {
  const reduced = useReducedMotion() ?? false;
  const sentences = splitSentences(answer.text);
  const plan = revealPlan(sentences.length, reduced);
  const byNumber = new Map(answer.passages.map((p) => [p.number, p]));
  const uncited = new Set(answer.citations.uncited_sentences.map((s) => s.trim()));
  const seconds = answer.timings.rewrite + answer.timings.retrieve + answer.timings.generate;
  const fade = (delayMs: number) =>
    reduced ? { initial: false as const } : {
      initial: { opacity: 0 },
      animate: { opacity: 1 },
      transition: { delay: delayMs / 1000, duration: plan.fadeMs / 1000, ease: "easeOut" as const },
    };

  return (
    <article className="space-y-3">
      <p className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
        <span aria-hidden className="size-1.5 rounded-full bg-teal" />
        {answer.passages.length} passage{answer.passages.length === 1 ? "" : "s"} read · {seconds.toFixed(1)} s
      </p>
      <p className="text-lg leading-relaxed text-text">
        {sentences.map((sentence, index) => (
          <motion.span
            key={index}
            {...fade(plan.sentenceDelays[index] ?? 0)}
            {...(uncited.has(sentence.trim()) && {
              "data-uncited": "",
              title: "This sentence has no citation",
              className: "underline decoration-amber/70 decoration-dotted underline-offset-4",
            })}
          >
            {splitSegments(sentence).map((segment, i) =>
              segment.kind === "text" ? (
                <span key={i}>{segment.text}</span>
              ) : (
                <motion.span key={i} {...fade(plan.chipsDelay)}>
                  {segment.numbers.map((number) => (
                    <CitationChip key={number} number={number} passage={byNumber.get(number)} onOpen={onOpenCitation} />
                  ))}
                </motion.span>
              ),
            )}{" "}
          </motion.span>
        ))}
      </p>
      <UncitedFlag count={uncited.size} />
      {answer.verified && (
        <motion.div {...fade(plan.badgeDelay)}>
          <VerifiedBadge />
        </motion.div>
      )}
    </article>
  );
}
