import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { splitSentences } from "@/lib/sentences";

// Shared with tests/test_sentences.py, so the UI's sentences line up with the engine's report.
const CASES: { name: string; text: string; sentences: string[] }[] = JSON.parse(
  readFileSync(join(__dirname, "..", "..", "tests", "fixtures", "sentence_cases.json"), "utf-8"),
);

describe("splitSentences", () => {
  it.each(CASES)("$name", ({ text, sentences }) => {
    expect(splitSentences(text)).toEqual(sentences);
  });
});
