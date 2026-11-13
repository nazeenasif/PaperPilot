import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { describe, expect, it, vi } from "vitest";

import { HighlightOverlay } from "@/components/source/HighlightOverlay";
import { SourceViewer } from "@/components/source/SourceViewer";
import { scaleRegion } from "@/lib/geometry";
import type { NumberedPassage, PassageView } from "@/lib/types";

// react-pdf needs a canvas and a worker; a sized placeholder stands in for the page.
vi.mock("react-pdf", () => ({
  pdfjs: { GlobalWorkerOptions: {} },
  Document: ({ children }: { children: React.ReactNode }) => <div data-testid="pdf-document">{children}</div>,
  Page: ({ pageNumber, width, onLoadSuccess }: { pageNumber: number; width: number; onLoadSuccess?: () => void }) => {
    useEffect(() => onLoadSuccess?.(), [onLoadSuccess]);
    return <div data-testid="pdf-page" data-page={pageNumber} style={{ width }} />;
  },
}));

const CITED: NumberedPassage = {
  number: 3,
  passage_id: "lora-12",
  paper_id: "lora",
  title: "LoRA: Low-Rank Adaptation of Large Language Models",
  section: "Our Method",
  page: 5,
  score: 0.741,
  text: "LoRA also has its limitations.",
};

function view(overrides: Partial<PassageView> = {}): PassageView {
  return {
    passage_id: "lora-12",
    paper_id: "lora",
    title: CITED.title,
    section: "Our Method",
    page: 5,
    page_count: 26,
    kind: "text",
    text: "LoRA also has its limitations. For example, it is not straightforward to batch inputs.",
    has_pdf: true,
    layout: {
      pages: [
        { number: 5, width: 612, height: 792 },
        { number: 6, width: 612, height: 792 },
      ],
      regions: [
        { page: 5, x0: 100, y0: 400, x1: 500, y1: 412 },
        { page: 5, x0: 100, y0: 414, x1: 480, y1: 426 },
        { page: 6, x0: 100, y0: 72, x1: 300, y1: 84 },
      ],
    },
    layout_reason: null,
    can_reprocess: false,
    ...overrides,
  };
}

function mockPassage(body: PassageView, extra?: (url: string, init?: RequestInit) => Response | undefined) {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    const custom = extra?.(url, init);
    if (custom) return Promise.resolve(custom);
    return Promise.resolve(new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderViewer(onClose = vi.fn()) {
  render(<SourceViewer citation={CITED} onClose={onClose} pageWidth={306} />);
  return onClose;
}

describe("scaleRegion and HighlightOverlay", () => {
  it("scales PDF points to pixels", () => {
    expect(scaleRegion({ page: 5, x0: 100, y0: 400, x1: 500, y1: 412 }, 0.5)).toEqual({
      left: 50, top: 200, width: 200, height: 6,
    });
  });

  it("draws one labelled box per region on the page", () => {
    render(<HighlightOverlay regions={view().layout!.regions} page={5} scale={0.5} />);
    const overlay = screen.getByRole("img", { name: /highlighted passage/i });
    const boxes = overlay.querySelectorAll("[data-region]");
    expect(boxes).toHaveLength(2);
    expect((boxes[0] as HTMLElement).style.left).toBe("50px");
    expect((boxes[0] as HTMLElement).style.top).toBe("200px");
  });
});

describe("SourceViewer", () => {
  it("shows the paper, section, page, score and the highlighted page", async () => {
    const fetchMock = mockPassage(view());
    renderViewer();
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(CITED.title)).toBeInTheDocument();
    expect(within(dialog).getByText(/Our Method · page 5 of 26/)).toBeInTheDocument();
    expect(within(dialog).getByText(/score 0\.741/)).toBeInTheDocument();
    expect(await within(dialog).findByTestId("pdf-page")).toHaveAttribute("data-page", "5");
    expect(within(dialog).getByRole("img", { name: /highlighted passage/i })).toBeInTheDocument();
    expect(within(dialog).getByText(/highlighted text is exactly what the model read/i)).toBeInTheDocument();
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8000/api/passages/lora-12");
  });

  it("shows regions that continue on the next page", async () => {
    mockPassage(view());
    const user = userEvent.setup();
    renderViewer();
    expect(await screen.findByText(/continues on page 6/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /next page/i }));
    expect(await screen.findByTestId("pdf-page")).toHaveAttribute("data-page", "6");
    expect(screen.getByRole("img", { name: /highlighted passage/i }).querySelectorAll("[data-region]")).toHaveLength(1);
  });

  it("links to the full PDF at the cited page", async () => {
    mockPassage(view());
    renderViewer();
    const link = await screen.findByRole("link", { name: /open full pdf/i });
    expect(link).toHaveAttribute("href", "http://127.0.0.1:8000/api/papers/lora/pdf#page=5");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("shows the passage text beside the page when the location could not be marked", async () => {
    mockPassage(view({ layout: null, layout_reason: "unavailable" }));
    renderViewer();
    expect(await screen.findByText(/exact location could not be marked/i)).toBeInTheDocument();
    expect(screen.getByText(/not straightforward to batch inputs/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /re-process/i })).not.toBeInTheDocument();
  });

  it("offers re-processing after a layout mismatch", async () => {
    const fetchMock = mockPassage(view({ layout: null, layout_reason: "mismatch", can_reprocess: true }), (url) =>
      url.endsWith("/reprocess")
        ? new Response(JSON.stringify({ job_id: "j1", file_name: CITED.title }), {
            status: 202,
            headers: { "Content-Type": "application/json" },
          })
        : undefined,
    );
    const user = userEvent.setup();
    renderViewer();
    await user.click(await screen.findByRole("button", { name: /re-process paper for exact highlights/i }));
    const call = fetchMock.mock.calls.find(([url]) => url.endsWith("/reprocess"));
    expect(call?.[0]).toBe("http://127.0.0.1:8000/api/papers/lora/reprocess");
    expect(new Headers(call?.[1]?.headers).get("X-PaperPilot")).toBe("1");
    expect(await screen.findByText(/re-processing started/i)).toBeInTheDocument();
  });

  it("explains how to get the PDF when it is not stored", async () => {
    mockPassage(view({ has_pdf: false, layout: null, layout_reason: "no_pdf" }));
    renderViewer();
    expect(await screen.findByText(/add the paper.s file again/i)).toBeInTheDocument();
    expect(screen.getByText(/not straightforward to batch inputs/)).toBeInTheDocument();
    expect(screen.queryByTestId("pdf-page")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /open full pdf/i })).not.toBeInTheDocument();
  });

  it("says when the passage is no longer in the library", async () => {
    mockPassage(view(), () =>
      new Response(JSON.stringify({ kind: "unknown_passage", passage_id: "lora-12" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );
    renderViewer();
    expect(await screen.findByText(/no longer in your library/i)).toBeInTheDocument();
  });

  it("closes with Escape", async () => {
    mockPassage(view());
    const user = userEvent.setup();
    const onClose = renderViewer();
    await screen.findByRole("dialog");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});

describe("opening the viewer from the Ask screen", () => {
  it("opens the cited passage from a chip, by click or Enter, and returns focus on Escape", async () => {
    const { AskScreen } = await import("@/components/ask/AskScreen");
    const answer = {
      question: "What is LoRA?", standalone_question: "What is LoRA?", rewrite_applied: false,
      rewrite_fallback_reason: null, text: "LoRA has limitations [3].", not_found: false, fallback_reason: null,
      warning: null, rejected_answer: null, citations: { valid: [3], invalid: [], uncited_sentences: [] },
      verified: true, passages: [CITED], papers_read: 1, word_count: 3, llm_calls: 1,
      requests: { planned: 1, retries: 0 }, timings: { rewrite: 0, retrieve: 0.1, generate: 5 }, tokens: {}, usage: null,
    };
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      if (url.endsWith("/api/ask")) {
        return Promise.resolve(new Response(`event: answer\ndata: ${JSON.stringify(answer)}\n\n`,
          { headers: { "Content-Type": "text/event-stream" } }));
      }
      return Promise.resolve(new Response(JSON.stringify(view()), { headers: { "Content-Type": "application/json" } }));
    }));
    const user = userEvent.setup();
    render(<AskScreen />);
    await user.type(screen.getByRole("textbox", { name: /ask about your papers/i }), "What is LoRA?{Enter}");
    const chip = await screen.findByRole("button", { name: /^Citation 3: LoRA/ });
    chip.focus();
    await user.keyboard("{Enter}");
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Our Method · page 5 of 26/)).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await waitFor(() => expect(chip).toHaveFocus());
  });
});
