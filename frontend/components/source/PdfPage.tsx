"use client";

// Loaded only in the browser (next/dynamic, ssr: false): pdf.js needs browser APIs.
import { Document, Page, pdfjs } from "react-pdf";

// The worker is copied from react-pdf's own pdfjs-dist by scripts/copy-pdf-worker.mjs.
pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

/** One page of a PDF, drawn `width` pixels wide, without text or annotation layers. */
export default function PdfPage({ url, page, width }: { url: string; page: number; width: number }) {
  return (
    <Document
      file={url}
      loading={<div className="flex h-96 items-center justify-center text-sm text-passage-text/70">Loading the page…</div>}
      error={<div className="p-4 text-sm text-passage-text">The PDF couldn&apos;t be shown.</div>}
    >
      <Page pageNumber={page} width={width} renderTextLayer={false} renderAnnotationLayer={false} />
    </Document>
  );
}
