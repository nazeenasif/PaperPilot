import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

// jsdom has no matchMedia; components ask it about reduced motion and screen width.
function mockMatchMedia(matches = false) {
  return vi.fn((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

beforeEach(() => {
  vi.stubGlobal("matchMedia", mockMatchMedia());
  // No test may reach the network (or the API, or the model): every test mocks fetch itself.
  vi.stubGlobal(
    "fetch",
    vi.fn((input: unknown) => {
      throw new Error(`Unmocked fetch in a test: ${String(input)}`);
    }),
  );
});

afterEach(() => {
  cleanup();
  // Screens remember choices for the tab (e.g. Compare's papers); no test may see another's.
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
