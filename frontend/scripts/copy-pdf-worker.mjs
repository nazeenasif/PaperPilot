// Copy the pdf.js worker that react-pdf depends on into public/, so the viewer loads it from
// this app (no CDN) and the worker always matches react-pdf's pdfjs-dist version (research R5).
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const requireFromReactPdf = createRequire(createRequire(import.meta.url).resolve("react-pdf/package.json"));
const pdfjsRoot = dirname(requireFromReactPdf.resolve("pdfjs-dist/package.json"));
const { version } = requireFromReactPdf("pdfjs-dist/package.json");

const source = join(pdfjsRoot, "build", "pdf.worker.min.mjs");
const target = join(here, "..", "public", "pdf.worker.min.mjs");
mkdirSync(dirname(target), { recursive: true });
copyFileSync(source, target);
console.log(`Copied pdf.js worker ${version} to public/pdf.worker.min.mjs`);
