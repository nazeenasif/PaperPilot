import { describe, expect, it } from "vitest";

import { REVEAL_CAP_MS, revealPlan } from "@/lib/reveal";
import { citationNumbers, splitSentences, splitSegments } from "@/lib/sentences";

describe("splitSentences (same rule as the engine's uncited-sentence check)", () => {
  it("splits on a full stop followed by a capital, digit, bracket or quote", () => {
    expect(splitSentences("LoRA is efficient [3]. It allows task switching [3].")).toEqual([
      "LoRA is efficient [3].",
      "It allows task switching [3].",
    ]);
  });

  it("keeps a citation that follows the full stop with its sentence", () => {
    expect(splitSentences("LoRA is efficient. [3] It allows task switching. [1, 2]")).toEqual([
      "LoRA is efficient. [3]",
      "It allows task switching. [1, 2]",
    ]);
  });

  it("does not split inside a sentence such as 'e.g. the' or '0.5'", () => {
    expect(splitSentences("Ranks such as 0.5 work, e.g. the small ones [2].")).toEqual([
      "Ranks such as 0.5 work, e.g. the small ones [2].",
    ]);
  });

  it("splits lines and drops list bullets", () => {
    expect(splitSentences("- First point [1].\n- Second point [2].")).toEqual(["First point [1].", "Second point [2]."]);
  });

  it("returns the not-found sentence unchanged", () => {
    expect(splitSentences("I couldn't find that in the selected papers.")).toEqual([
      "I couldn't find that in the selected papers.",
    ]);
  });
});

describe("splitSegments and citationNumbers", () => {
  it("separates text from citation groups", () => {
    expect(splitSegments("Trained on WMT [2, 4] and tested [5-6].")).toEqual([
      { kind: "text", text: "Trained on WMT " },
      { kind: "citation", numbers: [2, 4] },
      { kind: "text", text: " and tested " },
      { kind: "citation", numbers: [5, 6] },
      { kind: "text", text: "." },
    ]);
  });

  it("expands ranges, including en dashes", () => {
    expect(citationNumbers("2–4")).toEqual([2, 3, 4]);
    expect(citationNumbers("1, 3-4")).toEqual([1, 3, 4]);
  });

  it("leaves bracketed text that is not a citation alone", () => {
    expect(splitSegments("A matrix [W] here.")).toEqual([{ kind: "text", text: "A matrix [W] here." }]);
  });
});

describe("revealPlan (FR-011: under 500 ms, never typing-paced)", () => {
  it("staggers sentences 40 ms apart, then chips, then the badge", () => {
    const plan = revealPlan(3, false);
    expect(plan.sentenceDelays).toEqual([0, 40, 80]);
    expect(plan.chipsDelay).toBeGreaterThan(80);
    expect(plan.badgeDelay).toBeGreaterThan(plan.chipsDelay);
    expect(plan.fadeMs).toBe(160);
    expect(plan.totalMs).toBe(plan.badgeDelay + plan.fadeMs);
  });

  it.each([1, 2, 4, 5, 10, 40])("keeps %i sentences within the cap", (count) => {
    const plan = revealPlan(count, false);
    expect(plan.sentenceDelays).toHaveLength(count);
    expect(plan.totalMs).toBeLessThanOrEqual(REVEAL_CAP_MS);
    expect(REVEAL_CAP_MS).toBeLessThanOrEqual(450);
    for (let i = 1; i < count; i++) expect(plan.sentenceDelays[i]!).toBeGreaterThanOrEqual(plan.sentenceDelays[i - 1]!);
  });

  it("shows everything at once with reduced motion", () => {
    const plan = revealPlan(6, true);
    expect(plan.sentenceDelays.every((d) => d === 0)).toBe(true);
    expect([plan.chipsDelay, plan.badgeDelay, plan.fadeMs, plan.totalMs]).toEqual([0, 0, 0, 0]);
  });
});
