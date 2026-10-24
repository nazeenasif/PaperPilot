// Smoke tests: the real frontend against a fake backend (e2e/fake-backend.ts). One test per
// user story; run one with `npm run test:e2e -- -g "US1"`.

import { expect, test, type Locator } from "@playwright/test";

import { fakeBackend, fakeLibrary } from "./fake-backend";
import { makePdf } from "./pdf";

/** Drop files on an element the way a browser does (a drop event carrying a DataTransfer). */
async function dropFiles(target: Locator, files: { name: string; buffer: Buffer }[]) {
  const payload = files.map((file) => ({ name: file.name, data: file.buffer.toString("base64") }));
  await target.evaluate((zone, items) => {
    const transfer = new DataTransfer();
    for (const item of items) {
      const bytes = Uint8Array.from(atob(item.data), (c) => c.charCodeAt(0));
      transfer.items.add(new File([bytes], item.name, { type: "application/pdf" }));
    }
    zone.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: transfer }));
  }, payload);
}

test("US1 ask", async ({ page }) => {
  const backend = await fakeBackend(page, { askDelayMs: 800 });
  await page.goto("/");

  const box = page.getByRole("textbox", { name: /ask about your papers/i });
  await box.fill("What is LoRA?");
  await box.press("Enter");

  // Working state first, and no answer text until the checked answer arrives (FR-011).
  await expect(page.getByText("Searching your papers…")).toBeVisible();
  await expect(page.getByText(/efficient adaptation strategy/)).toHaveCount(0);

  await expect(page.getByText(/efficient adaptation strategy/)).toBeVisible();
  await expect(page.getByRole("button", { name: /^Citation 1: LoRA/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Citation 2: LoRA/ })).toBeVisible();
  await expect(page.getByText("All citations verified")).toBeVisible();
  await expect(page.getByText(/2 passages read · 8\.8 s/)).toBeVisible();
  expect(backend.asks).toEqual([{ question: "What is LoRA?" }]);
});

test("US2 viewer", async ({ page }) => {
  await fakeBackend(page);
  await page.goto("/");
  const box = page.getByRole("textbox", { name: /ask about your papers/i });
  await box.fill("What is LoRA?");
  await box.press("Enter");

  // Citation 1: the PDF page is drawn and the passage is highlighted on it.
  await page.getByRole("button", { name: /^Citation 1: LoRA/ }).click();
  const viewer = page.getByRole("dialog");
  await expect(viewer.getByText(/Our Method · page 1 of 1/)).toBeVisible();
  await expect(viewer.locator(".react-pdf__Page canvas")).toBeVisible({ timeout: 15_000 });
  const highlight = viewer.getByRole("img", { name: /highlighted passage/i });
  await expect(highlight).toBeVisible();
  await expect(highlight.locator("[data-region]")).toHaveCount(2);
  const regionBox = await highlight.locator("[data-region]").first().boundingBox();
  expect(regionBox?.width ?? 0).toBeGreaterThan(10);
  await expect(viewer.getByRole("link", { name: /open full pdf/i })).toHaveAttribute(
    "href", "http://127.0.0.1:8000/api/papers/lora/pdf#page=1");

  // Escape closes the viewer and returns focus to the chip.
  await page.keyboard.press("Escape");
  await expect(viewer).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Citation 1: LoRA/ })).toBeFocused();

  // Citation 2: no exact location, so the passage text is shown beside the page.
  await page.getByRole("button", { name: /^Citation 2: LoRA/ }).click();
  await expect(page.getByRole("dialog").getByText(/exact location could not be marked/i)).toBeVisible();
  await expect(page.getByRole("dialog").getByText("LoRA allows quick task switching when deployed as a service.")).toBeVisible();
});

test("US3 library", async ({ page }) => {
  const library = fakeLibrary();
  await fakeBackend(page, { routes: library.routes });
  await page.goto("/library");
  const heading = page.getByRole("heading", { level: 1 });
  await expect(heading).toHaveText("2 papers, 75 searchable passages");
  await expect(page.getByText(/embeddings run on this machine/i)).toBeVisible();

  // Two files dropped at once: a new paper goes through every phase; a known one is attached.
  const zone = page.getByRole("region", { name: /add papers/i });
  await dropFiles(zone, [
    { name: "new-paper.pdf", buffer: makePdf(["A Small Study of Grounded Answers"]) },
    { name: "attention.pdf", buffer: makePdf(["Attention Is All You Need"]) },
  ]);
  const uploads = page.getByRole("list", { name: "Uploads" });
  await expect(uploads.getByText("Mapping highlights")).toBeVisible();
  await expect(uploads.getByText("Embedding passages · 80%")).toBeVisible();
  await expect(uploads.getByText("Added to your library")).toBeVisible();
  await expect(uploads.getByText("PDF attached", { exact: true })).toBeVisible();
  await expect(heading).toHaveText("3 papers, 78 searchable passages");
  await expect(page.getByRole("heading", { name: "A Small Study of Grounded Answers" })).toBeVisible();

  // The same content under another name is recognised without processing.
  await dropFiles(zone, [{ name: "bert renamed.pdf", buffer: makePdf(["BERT"]) }]);
  await expect(uploads.getByText("Already in your library")).toBeVisible();
  await expect(uploads.getByRole("link", { name: /view the paper/i })).toHaveAttribute("href", "#paper-bert");
  expect(library.uploads).toEqual([["new-paper.pdf", "attention.pdf"], ["bert renamed.pdf"]]);

  // Delete asks first; cancelling keeps the paper.
  const remove = page.getByRole("button", { name: "Delete A Small Study of Grounded Answers" });
  await remove.click();
  await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(heading).toHaveText("3 papers, 78 searchable passages");
  await remove.click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete paper" }).click();
  await expect(heading).toHaveText("2 papers, 75 searchable passages");
  await expect(page.getByRole("heading", { name: "A Small Study of Grounded Answers" })).toHaveCount(0);
  expect(library.writeHeaders).toEqual(["1", "1", "1"]);
});
