// FR-031 / SC-009: every text/background pair from the design tokens meets WCAG 4.5:1.
// Reads app/globals.css, so a token change that breaks contrast fails here (research R12).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

// Vitest runs from frontend/ (import.meta.url is not a file: URL under jsdom).
const css = readFileSync(join(process.cwd(), "app", "globals.css"), "utf8");

/** Every `--name: #rrggbb` declaration, with Tailwind's "color-" prefix removed. */
function readTokens(source: string): Record<string, string> {
  const tokens: Record<string, string> = {};
  for (const match of source.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\b/g)) {
    tokens[match[1]!.replace(/^color-/, "")] = match[2]!.toLowerCase();
  }
  return tokens;
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)) as [
    number,
    number,
    number,
  ];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG 2.x contrast ratio between two colours. */
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

const tokens = readTokens(css);

// [text token, background token, where it is used]
const PAIRS: [string, string, string][] = [
  ["text", "ink", "body text on the page background"],
  ["text", "panel", "text on cards and panels"],
  ["text", "panel-2", "text on raised panels"],
  ["muted-foreground", "ink", "secondary text on the page"],
  ["muted-foreground", "panel", "secondary text on panels"],
  ["muted-foreground", "panel-2", "secondary text on raised panels"],
  ["teal", "ink", "verified badge and links on the page"],
  ["teal", "panel", "verified badge on panels"],
  ["amber", "ink", "citation numbers on the page"],
  ["amber", "panel", "citation numbers and warnings on panels"],
  ["ink", "teal", "teal buttons"],
  ["ink", "amber", "amber citation chips"],
  ["passage-text", "highlight", "highlighted passage in the source viewer"],
  ["passage-text", "page", "PDF page text around the highlight"],
  ["foreground", "background", "shadcn: default text"],
  ["card-foreground", "card", "shadcn: cards"],
  ["popover-foreground", "popover", "shadcn: popovers and tooltips"],
  ["primary-foreground", "primary", "shadcn: primary buttons"],
  ["secondary-foreground", "secondary", "shadcn: secondary buttons"],
  ["muted-foreground", "muted", "shadcn: muted surfaces"],
  ["accent-foreground", "accent", "shadcn: hovered items"],
];

describe("design token contrast (WCAG 4.5:1)", () => {
  it.each(PAIRS)("%s on %s (%s)", (text, background) => {
    expect(tokens[text], `token --${text} missing from globals.css`).toBeDefined();
    expect(tokens[background], `token --${background} missing from globals.css`).toBeDefined();
    expect(contrast(tokens[text]!, tokens[background]!)).toBeGreaterThanOrEqual(4.5);
  });

  it("catches a colour that is too dark (#6B7280 on panel measures about 3.8:1)", () => {
    const ratio = contrast("#6b7280", tokens.panel!);
    expect(ratio).toBeLessThan(4.5);
    expect(ratio).toBeCloseTo(3.82, 1);
  });

  it("matches the ratios measured in research R12", () => {
    expect(contrast(tokens.text!, tokens.panel!)).toBeCloseTo(15.28, 1);
    expect(contrast(tokens.teal!, tokens.ink!)).toBeCloseTo(13.47, 1);
    expect(contrast(tokens["muted-foreground"]!, tokens.panel!)).toBeCloseTo(6.1, 1);
  });
});
