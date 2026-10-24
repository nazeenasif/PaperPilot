// Timing of the verified answer's entrance (FR-011, research R6): sentences fade in one after
// another, then the citation chips, then the badge; under 500 ms in total and never paced
// like typing. With reduced motion everything appears at once.

export const REVEAL_CAP_MS = 450;
const STAGGER_MS = 40;
const FADE_MS = 160;
const GAP_MS = 80; // after the last sentence starts: chips; then the badge

export interface RevealPlan {
  sentenceDelays: number[];
  chipsDelay: number;
  badgeDelay: number;
  fadeMs: number;
  totalMs: number;
}

/** Delays (ms) for each sentence, the chips and the badge; long answers get a tighter stagger. */
export function revealPlan(sentenceCount: number, reducedMotion: boolean): RevealPlan {
  const count = Math.max(sentenceCount, 0);
  if (reducedMotion) {
    return { sentenceDelays: Array<number>(count).fill(0), chipsDelay: 0, badgeDelay: 0, fadeMs: 0, totalMs: 0 };
  }
  const fixed = 2 * GAP_MS + FADE_MS;
  const room = (REVEAL_CAP_MS - fixed) / Math.max(count - 1, 1);
  const stagger = count > 1 ? Math.min(STAGGER_MS, Math.floor(room * 100) / 100) : 0;
  const sentenceDelays = Array.from({ length: count }, (_, i) => i * stagger);
  const lastStart = count > 0 ? (count - 1) * stagger : 0;
  const chipsDelay = lastStart + GAP_MS;
  const badgeDelay = chipsDelay + GAP_MS;
  return { sentenceDelays, chipsDelay, badgeDelay, fadeMs: FADE_MS, totalMs: badgeDelay + FADE_MS };
}
