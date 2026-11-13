import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SourceViewer } from "@/components/source/SourceViewer";

import { PASSAGES } from "./summary-fixtures";

vi.mock("react-pdf", () => ({ Document: () => null, Page: () => null, pdfjs: { GlobalWorkerOptions: {} } }));

describe("A citation whose passage changed when the paper was re-processed", () => {
  it("shows the passage as cited and does not open the id, which may now hold other text", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<SourceViewer citation={{ ...PASSAGES[0]!, moved: true, text: "The passage as it was." }} onClose={() => {}} />);
    expect(await screen.findByText("The passage as it was.")).toBeInTheDocument();
    expect(screen.getByText(/changed when this paper was re-processed/i)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
