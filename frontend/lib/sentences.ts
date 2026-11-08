// Sentence and citation parsing that mirrors the engine (paperpilot/prompts.py), so the UI's
// sentences line up with the engine's citation report (uncited sentences, FR-008a).

/** A citation group: [2], [2, 4], [2-4], [2–4]. Same pattern as prompts._CITATION. */
const CITATION = /\[\s*(\d+(?:\s*[-–,]\s*\d+)*)\s*\]/g;
/** List bullets removed before splitting, as in prompts._BULLET. */
const BULLET = /^\s*(?:[-*•]|\d+[.)])\s+/;
/** A sentence ends at . ! or ? followed by whitespace and a capital, digit, bracket or quote. */
const SENTENCE_END = /(?<=[.!?])\s+(?=[A-Z0-9[("'])/;
/** A sentence does not end after these. Same pattern as prompts._ABBREVIATION_END. */
const ABBREVIATION_END = /(?:^|[\s(])(?:et al|e\.g|i\.e|E\.g|I\.e|Fig|Eq|Sec|Tab|vs|cf|Cf)\.$/;

export type Segment = { kind: "text"; text: string } | { kind: "citation"; numbers: number[] };

/** Expand a citation group's inside ("2, 4", "2-4", "2–4") into its numbers. */
export function citationNumbers(group: string): number[] {
  const numbers: number[] = [];
  for (const part of group.split(",")) {
    const bounds = part.trim().split(/\s*[-–]\s*/).map(Number);
    const [start, end] = bounds as [number, number | undefined];
    if (bounds.length === 2 && end !== undefined && start <= end) {
      for (let n = start; n <= end; n++) numbers.push(n);
    } else {
      numbers.push(...bounds);
    }
  }
  return numbers;
}

function onlyCitations(piece: string): boolean {
  return piece.replace(CITATION, "").replace(/^[\s.,;]+|[\s.,;]+$/g, "") === "";
}

/** Split answer text into sentences exactly as the engine does. */
export function splitSentences(text: string): string[] {
  const sentences: string[] = [];
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.replace(BULLET, "").trim();
    let afterAbbreviation = false;
    for (const rawPiece of line.split(SENTENCE_END)) {
      const piece = rawPiece.trim();
      if (!piece) continue;
      if (afterAbbreviation || (sentences.length > 0 && onlyCitations(piece))) {
        sentences[sentences.length - 1] += ` ${piece}`;
      } else {
        sentences.push(piece);
      }
      afterAbbreviation = ABBREVIATION_END.test(piece);
    }
  }
  return sentences;
}

/** Split one sentence into text and citation segments for rendering chips. */
export function splitSegments(sentence: string): Segment[] {
  const segments: Segment[] = [];
  let last = 0;
  for (const match of sentence.matchAll(CITATION)) {
    const start = match.index ?? 0;
    if (start > last) segments.push({ kind: "text", text: sentence.slice(last, start) });
    segments.push({ kind: "citation", numbers: citationNumbers(match[1] ?? "") });
    last = start + match[0].length;
  }
  if (last < sentence.length) segments.push({ kind: "text", text: sentence.slice(last) });
  return segments;
}
