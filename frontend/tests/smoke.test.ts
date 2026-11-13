import { describe, expect, it } from "vitest";

describe("test setup", () => {
  it("blocks unmocked network calls", () => {
    expect(() => fetch("http://127.0.0.1:8000/api/status")).toThrow(/Unmocked fetch/);
  });

  it("provides matchMedia", () => {
    expect(window.matchMedia("(prefers-reduced-motion: reduce)").matches).toBe(false);
  });
});
