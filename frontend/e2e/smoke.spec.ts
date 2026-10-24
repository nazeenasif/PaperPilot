// Smoke tests: the real frontend against a fake backend (e2e/fake-backend.ts). One test per
// user story; run one with `npm run test:e2e -- -g "US1"`.

import { expect, test } from "@playwright/test";

import { fakeBackend } from "./fake-backend";

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
