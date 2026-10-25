import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LibraryHeader } from "@/components/library/LibraryHeader";
import { LibraryScreen } from "@/components/library/LibraryScreen";
import { PaperCard } from "@/components/library/PaperCard";
import { UploadRow } from "@/components/library/UploadRow";
import type { PaperCard as Paper, UploadJob } from "@/lib/types";

const encoder = new TextEncoder();

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** A fetch Response whose event stream the test feeds by hand. */
function controlledStream() {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({ start: (c) => void (controller = c) });
  return {
    response: new Response(body, { headers: { "Content-Type": "text/event-stream" } }),
    send(event: string, data: unknown) {
      controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
    },
  };
}

const ATTENTION: Paper = {
  paper_id: "att",
  title: "Attention Is All You Need",
  page_count: 15,
  passage_count: 33,
  text_passages: 29,
  table_passages: 4,
  section_count: 8,
  arxiv_id: "1706.03762",
  has_pdf: true,
  highlights: "exact",
};

function job(overrides: Partial<UploadJob> = {}): UploadJob {
  return {
    job_id: "j1",
    kind: "upload",
    file_name: "new-paper.pdf",
    phase: "queued",
    percent: null,
    outcome: null,
    highlights: null,
    paper_id: null,
    error: null,
    ...overrides,
  };
}

/** Route fetch by method and path; anything else fails the test. */
function routes(handlers: Record<string, (init: RequestInit) => Response | Promise<Response>>) {
  const fetchMock = vi.fn(async (input: unknown, init: RequestInit = {}) => {
    const path = new URL(String(input)).pathname;
    const handler = handlers[`${init.method ?? "GET"} ${path}`];
    if (!handler) throw new Error(`Unexpected request ${init.method ?? "GET"} ${path}`);
    return handler(init);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const PAPERS = { papers: [ATTENTION], total_passages: 33 };

describe("Adding files", () => {
  it("posts dropped files, several at once, as one multipart request with the write header", async () => {
    const stream = controlledStream();
    const fetchMock = routes({
      "GET /api/papers": () => json(PAPERS),
      "GET /api/jobs": () => json({ jobs: [] }),
      "GET /api/jobs/events": () => stream.response,
      "POST /api/papers": () => json({ jobs: [{ job_id: "j1", file_name: "a.pdf" }, { job_id: "j2", file_name: "b.pdf" }] }, 202),
    });
    render(<LibraryScreen />);
    const zone = await screen.findByRole("region", { name: /add papers/i });
    const files = [new File(["%PDF-a"], "a.pdf", { type: "application/pdf" }), new File(["%PDF-b"], "b.pdf", { type: "application/pdf" })];
    fireEvent.drop(zone, { dataTransfer: { files, types: ["Files"] } });
    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true));
    const [, init] = fetchMock.mock.calls.find(([, i]) => i?.method === "POST") as [string, RequestInit];
    expect((init.headers as Record<string, string>)["X-PaperPilot"]).toBe("1");
    const body = init.body as FormData;
    expect(body.getAll("files").map((f) => (f as File).name)).toEqual(["a.pdf", "b.pdf"]);
  });

  it("accepts several files from the file chooser", async () => {
    const stream = controlledStream();
    const fetchMock = routes({
      "GET /api/papers": () => json(PAPERS),
      "GET /api/jobs": () => json({ jobs: [] }),
      "GET /api/jobs/events": () => stream.response,
      "POST /api/papers": () => json({ jobs: [] }, 202),
    });
    const user = userEvent.setup();
    render(<LibraryScreen />);
    const files = [new File(["%PDF-a"], "a.pdf", { type: "application/pdf" }), new File(["%PDF-b"], "b.pdf", { type: "application/pdf" })];
    await user.upload(await screen.findByLabelText(/choose pdf files/i), files);
    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true));
    expect(screen.getByRole("button", { name: /choose files/i })).toBeInTheDocument();
  });
});

describe("Upload rows", () => {
  it("shows Parsing, Chunking, Embedding with a percentage, then Ready", () => {
    const { rerender } = render(<UploadRow job={job({ phase: "parsing" })} />);
    expect(screen.getByText("Parsing")).toHaveAttribute("data-state", "active");
    rerender(<UploadRow job={job({ phase: "chunking" })} />);
    expect(screen.getByText("Parsing")).toHaveAttribute("data-state", "done");
    expect(screen.getByText("Chunking")).toHaveAttribute("data-state", "active");
    rerender(<UploadRow job={job({ phase: "embedding", percent: 62 })} />);
    expect(screen.getByText("Embedding passages · 62%")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "62");
    rerender(<UploadRow job={job({ phase: "ready", outcome: "added", highlights: "exact", paper_id: "p" })} />);
    expect(screen.getByText("Ready")).toHaveAttribute("data-state", "done");
    expect(screen.getByText("Added to your library")).toBeInTheDocument();
  });

  it("shows an existing paper as already in the library, linking to its card", () => {
    render(<UploadRow job={job({ phase: "ready", outcome: "already_present", paper_id: "att", highlights: "exact" })} />);
    expect(screen.getByText("Already in your library")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view the paper/i })).toHaveAttribute("href", "#paper-att");
    expect(screen.queryByText("Parsing")).not.toBeInTheDocument();
  });

  it("shows Mapping highlights, then PDF attached", () => {
    const { rerender } = render(<UploadRow job={job({ phase: "mapping", paper_id: "att" })} />);
    expect(screen.getByText("Mapping highlights")).toBeInTheDocument();
    rerender(<UploadRow job={job({ phase: "ready", outcome: "pdf_attached", highlights: "exact", paper_id: "att" })} />);
    expect(screen.getByText("PDF attached")).toBeInTheDocument();
    rerender(<UploadRow job={job({ phase: "ready", outcome: "pdf_attached", highlights: "mismatch", paper_id: "att" })} />);
    expect(screen.getByText("PDF attached — exact highlights unavailable")).toBeInTheDocument();
  });

  it.each([
    ["not_pdf", "This file isn't a PDF.", /choose a \.pdf file/i],
    ["too_large", "This PDF is larger than 25 MB.", /smaller copy/i],
    ["no_text", "This PDF has no text PaperPilot can read.", /text-based version/i],
    ["unreadable", "This PDF couldn't be opened.", /download it again/i],
    ["password", "This PDF is password-protected.", /remove the password/i],
  ])("explains a %s failure with a next step", (reason, message, next) => {
    render(<UploadRow job={job({ phase: "failed", outcome: "failed", error: { kind: "upload_invalid", reason } })} />);
    const row = screen.getByRole("listitem");
    expect(within(row).getByText(message)).toBeInTheDocument();
    expect(within(row).getByText(next)).toBeInTheDocument();
    expect(row).not.toHaveTextContent(/upload_invalid|not_pdf|too_large|no_text|unreadable/);
  });

  it("shows Re-processed for a finished re-process", () => {
    render(<UploadRow job={job({ kind: "reprocess", file_name: "LoRA", phase: "ready", outcome: "reprocessed", highlights: "exact" })} />);
    expect(screen.getByText("Re-processed")).toBeInTheDocument();
  });
});

describe("Jobs", () => {
  it("updates rows from /api/jobs/events", async () => {
    const stream = controlledStream();
    routes({
      "GET /api/papers": () => json(PAPERS),
      "GET /api/jobs": () => json({ jobs: [] }),
      "GET /api/jobs/events": () => stream.response,
    });
    render(<LibraryScreen />);
    await screen.findByText("Attention Is All You Need");
    stream.send("job", job({ phase: "embedding", percent: 40 }));
    expect(await screen.findByText("Embedding passages · 40%")).toBeInTheDocument();
  });

  it("falls back to polling /api/jobs when the stream fails", async () => {
    let polls = 0;
    routes({
      "GET /api/papers": () => json(PAPERS),
      "GET /api/jobs": () => {
        polls += 1;
        return json({ jobs: [job({ phase: polls > 1 ? "chunking" : "parsing" })] });
      },
      "GET /api/jobs/events": () => json({ kind: "internal" }, 500),
    });
    render(<LibraryScreen />);
    expect(await screen.findByText("Chunking", { selector: "[data-state='active']" }, { timeout: 4000 })).toBeInTheDocument();
    expect(polls).toBeGreaterThan(1);
  });

  it("refreshes the cards when a job finishes", async () => {
    const stream = controlledStream();
    let listed = 0;
    routes({
      "GET /api/papers": () => {
        listed += 1;
        return json(listed > 1 ? { papers: [ATTENTION, { ...ATTENTION, paper_id: "new", title: "A New Paper" }], total_passages: 66 } : PAPERS);
      },
      "GET /api/jobs": () => json({ jobs: [] }),
      "GET /api/jobs/events": () => stream.response,
    });
    render(<LibraryScreen />);
    await screen.findByText("Attention Is All You Need");
    stream.send("job", job({ phase: "ready", outcome: "added", highlights: "exact", paper_id: "new" }));
    expect(await screen.findByText("A New Paper")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("2 papers, 66 searchable passages");
  });
});

describe("Paper cards", () => {
  it("shows the title, passages split into text and table, sections, pages and the arXiv ID", () => {
    render(<PaperCard paper={ATTENTION} onDeleted={() => undefined} />);
    const card = screen.getByRole("article");
    expect(within(card).getByRole("heading", { name: "Attention Is All You Need" })).toBeInTheDocument();
    expect(card).toHaveTextContent("33passages");
    expect(card).toHaveTextContent("8sections");
    expect(card).toHaveTextContent("15pages");
    expect(card).toHaveTextContent("29 text · 4 table");
    expect(card).toHaveTextContent("arXiv 1706.03762");
    expect(card).toHaveAttribute("id", "paper-att");
  });

  it("links Ask this paper to the Ask screen with only that paper", () => {
    render(<PaperCard paper={ATTENTION} onDeleted={() => undefined} />);
    expect(screen.getByRole("link", { name: /ask this paper/i })).toHaveAttribute("href", "/?paper=att");
  });

  it("asks for confirmation before deleting; cancel changes nothing", async () => {
    const fetchMock = routes({ "DELETE /api/papers/att": () => json({ removed_passages: 33 }) });
    const onDeleted = vi.fn();
    const user = userEvent.setup();
    render(<PaperCard paper={ATTENTION} onDeleted={onDeleted} />);
    await user.click(screen.getByRole("button", { name: /delete attention is all you need/i }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent(/33 passages/);
    await user.click(within(dialog).getByRole("button", { name: /cancel/i }));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(onDeleted).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /delete attention is all you need/i }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: /^delete paper$/i }));
    await waitFor(() => expect(onDeleted).toHaveBeenCalledWith("att"));
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("DELETE");
    expect((init.headers as Record<string, string>)["X-PaperPilot"]).toBe("1");
  });

  it("offers re-processing when exact highlights are unavailable", async () => {
    const fetchMock = routes({ "POST /api/papers/att/reprocess": () => json({ job_id: "r1", file_name: "Attention" }, 202) });
    const user = userEvent.setup();
    render(<PaperCard paper={{ ...ATTENTION, highlights: "mismatch" }} onDeleted={() => undefined} />);
    await user.click(screen.getByRole("button", { name: /re-process for exact highlights/i }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  });
});

describe("Header and what is not shown", () => {
  it("summarises the library and says embeddings run on this machine", () => {
    render(<LibraryHeader papers={5} passages={223} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("5 papers, 223 searchable passages");
    expect(screen.getByText(/embeddings run on this machine/i)).toBeInTheDocument();
  });

  it("uses the singular for one paper and one passage", () => {
    render(<LibraryHeader papers={1} passages={1} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("1 paper, 1 searchable passage");
  });

  it("offers Summarize on each card (Feature 4) and no Compare inside the Library", async () => {
    const stream = controlledStream();
    routes({
      "GET /api/papers": () => json(PAPERS),
      "GET /api/jobs": () => json({ jobs: [] }),
      "GET /api/jobs/events": () => stream.response,
    });
    render(<LibraryScreen />);
    await screen.findByText("Attention Is All You Need");
    expect(screen.getByRole("link", { name: "Summarize" })).toHaveAttribute("href", "/summarize/att");
    expect(screen.queryByText(/compare/i)).not.toBeInTheDocument();
  });
});
