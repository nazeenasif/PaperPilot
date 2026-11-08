import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Header } from "@/components/app/Header";
import { TurnFailure } from "@/components/states/TurnFailure";

const pathname = vi.hoisted(() => ({ value: "/" }));
vi.mock("next/navigation", () => ({ usePathname: () => pathname.value }));

describe("Header navigation (Feature 4)", () => {
  it("has four tabs: Ask, Library, Summarize, Compare", () => {
    render(<Header />);
    const nav = screen.getByRole("navigation", { name: "Main" });
    const links = Array.from(nav.querySelectorAll("a")).map((a) => [a.textContent, a.getAttribute("href")]);
    expect(links).toEqual([
      ["Ask", "/"],
      ["Library", "/library"],
      ["Summarize", "/summarize"],
      ["Compare", "/compare"],
    ]);
  });

  it.each([
    ["/summarize", "Summarize"],
    ["/summarize/a7b7a17d0cf9", "Summarize"],
    ["/compare", "Compare"],
    ["/library", "Library"],
    ["/", "Ask"],
  ])("marks the current tab for %s", (path, current) => {
    pathname.value = path;
    render(<Header />);
    expect(screen.getByRole("link", { current: "page" })).toHaveTextContent(current);
    expect(screen.getAllByRole("link", { current: "page" })).toHaveLength(1);
  });
});

describe("One model task at a time", () => {
  it.each(["busy_task"])("explains %s as another task still running", (kind) => {
    render(<TurnFailure kind={kind} fields={{}} question="What is LoRA?" onRetry={() => undefined} />);
    expect(screen.getByText("PaperPilot is still working on another answer, summary or comparison.")).toBeInTheDocument();
  });
});
