// Smoke tests: the real frontend against a fake backend (e2e/fake-backend.ts). One test per
// user story; run one with `npm run test:e2e -- -g "US1"`.

import { expect, test, type Locator, type Page } from "@playwright/test";

import { CORS, eventStream, fakeBackend, fakeLibrary, streamAskInPage, streamPostInPage } from "./fake-backend";
import {
  ANSWER,
  FOLLOW_UP_ANSWER,
  HELD_BACK_ANSWER,
  LIBRARY_PAPERS,
  LORA_CARD,
  LORA_SUMMARY,
  NOT_FOUND_ANSWER,
  NOT_FOUND_TEXT,
  SCOPED_ANSWER,
  SUMMARY_STEPS,
  USAGE,
} from "./fixtures";
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

async function askOnPage(page: Page, question = "What is LoRA?") {
  const box = page.getByRole("textbox", { name: /ask about your papers/i });
  await box.fill(question);
  await box.press("Enter");
  return box;
}

test("US5 states: not found", async ({ page }) => {
  await fakeBackend(page, { askEvents: [["progress", { step: "searching" }], ["answer", NOT_FOUND_ANSWER]] });
  await page.goto("/");
  await expect(page.getByRole("status", { name: /requests today/i })).toContainText("34 / 50");
  const box = await askOnPage(page, "What is the capital of France?");
  await expect(page.getByText(NOT_FOUND_TEXT)).toBeVisible();
  await expect(page.getByText(/only answers from your library/i)).toBeVisible();
  await page.getByRole("button", { name: "Rephrase more specifically" }).click();
  await expect(box).toBeFocused();
});

test("US5 states: busy countdown", async ({ page }) => {
  await streamAskInPage(page, [
    { afterMs: 50, event: "progress", data: { step: "generating" } },
    { afterMs: 50, event: "retry_wait", data: { attempt: 1, max_attempts: 4, wait_seconds: 8, reason: "rate_limited" } },
    { afterMs: 3_000, event: "answer", data: ANSWER },
  ]);
  await fakeBackend(page);
  await page.goto("/");
  await askOnPage(page);
  await expect(page.getByText("attempt 2 of 4")).toBeVisible();
  await expect(page.getByText("The free model is busy right now")).toBeVisible();
  await expect(page.getByText("0:08")).toBeVisible();
  await expect(page.getByText(/^0:0[5-7]$/)).toBeVisible({ timeout: 2_900 }); // it counts down live
  await expect(page.getByText(/efficient adaptation strategy/)).toBeVisible();
  await expect(page.getByText("attempt 2 of 4")).toHaveCount(0);
});

test("US5 states: daily limit with browse passages", async ({ page }) => {
  await fakeBackend(page, {
    usage: { ...USAGE, used: 50, remaining: 0 },
    askEvents: [["error", { kind: "daily_limit", used: 50, limit: 50, resets_at: "2026-10-26T00:00:00Z" }]],
  });
  await page.goto("/");
  await expect(page.getByRole("button", { name: /daily limit reached/i })).toBeVisible();
  await askOnPage(page);
  const state = page.getByRole("alert").filter({ hasText: "free requests used today" });
  await expect(state.getByText("50 / 50")).toBeVisible();
  await expect(state.getByText(/Answers resume at \d\d:\d\d your time/)).toBeVisible();
  await state.getByRole("button", { name: "Browse passages instead" }).click();
  const results = state.getByRole("list", { name: /matching passages/i });
  await expect(results.getByText("LoRA: Low-Rank Adaptation of Large Language Models")).toBeVisible();
  await expect(results.getByText("Our Method · page 1")).toBeVisible();
});

test("US5 states: held back with the unverified answer", async ({ page }) => {
  await fakeBackend(page, { askEvents: [["answer", HELD_BACK_ANSWER]] });
  await page.goto("/");
  await askOnPage(page);
  await expect(page.getByText(/The model cited passage 7, but only 2 were provided/)).toBeVisible();
  await expect(page.getByText("server wording")).toHaveCount(0);
  await page.getByRole("button", { name: "View the unverified answer" }).click();
  await expect(page.getByText("Not verified")).toBeVisible();
  await expect(page.getByText(/trains low-rank update matrices/)).toBeVisible();
  await expect(page.getByLabel("Citation 7: not among the provided passages")).toBeVisible();
});

test("US5 states: server unreachable, then recovered", async ({ page }) => {
  let down = true;
  await fakeBackend(page, {
    routes: {
      "/api/status": async (route) => {
        if (down) await route.abort("connectionrefused");
        else await route.fallback();
      },
    },
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Can't reach PaperPilot" })).toBeVisible();
  await expect(page.getByText(/reconnects by itself/i)).toBeVisible();
  down = false;
  await expect(page.getByRole("textbox", { name: /ask about your papers/i })).toBeVisible({ timeout: 10_000 });
});

test("US4 scope", async ({ page }) => {
  const asks: unknown[] = [];
  const answers = [SCOPED_ANSWER, FOLLOW_UP_ANSWER];
  await fakeBackend(page, {
    routes: {
      "/api/papers": async (route) => {
        const total = LIBRARY_PAPERS.reduce((sum, p) => sum + p.passage_count, 0);
        await route.fulfill({ status: 200, headers: CORS, json: { papers: LIBRARY_PAPERS, total_passages: total } });
      },
      "/api/ask": async (route) => {
        asks.push(route.request().postDataJSON());
        const answer = answers[Math.min(asks.length - 1, answers.length - 1)];
        await route.fulfill({
          status: 200,
          headers: { ...CORS, "content-type": "text/event-stream" },
          body: eventStream([["progress", { step: "searching" }], ["answer", answer]]),
        });
      },
    },
  });
  // "Ask this paper" on BERT's card links here.
  await page.goto("/?paper=bert");

  // The scope is a sidebar on wide screens and a sheet on phones.
  const onPhone = (page.viewportSize()?.width ?? 1280) < 1024; // Tailwind's lg breakpoint
  if (onPhone) await page.getByRole("button", { name: /choose papers/i }).click();
  const scope = page.getByRole("region", { name: "Search scope" }).filter({ visible: true });
  await expect(scope).toContainText("Search scope · 1 of 2 papers");
  await expect(scope.getByRole("checkbox", { name: /^BERT/ })).toBeChecked();
  await expect(scope.getByRole("checkbox", { name: /Attention/ })).not.toBeChecked();
  await expect(scope.getByText("42 passages")).toBeVisible();
  if (onPhone) await page.keyboard.press("Escape");

  await askOnPage(page, "What data was BERT pre-trained on?");
  await expect(page.getByText(/BooksCorpus and English Wikipedia/)).toBeVisible();
  await askOnPage(page, "How many words does it contain?");
  await expect(page.getByText(`Searched as "How many words does BERT's pre-training data contain?"`)).toBeVisible();
  await expect(page.getByText(/800M words and English Wikipedia/)).toBeVisible();

  expect(asks[0]).toEqual({ question: "What data was BERT pre-trained on?", paper_ids: ["bert"] });
  expect(asks[1]).toEqual({
    question: "How many words does it contain?",
    paper_ids: ["bert"],
    history: [
      { role: "user", text: "What data was BERT pre-trained on?" },
      { role: "assistant", text: SCOPED_ANSWER.text },
    ],
  });

  await page.getByRole("button", { name: "New conversation" }).click();
  await expect(page.getByText(/BooksCorpus and English Wikipedia/)).toHaveCount(0);
});

// --- Phone width and keyboard (SC-008, FR-029, FR-030) ---

/** The page must never scroll sideways (375 px in the phone project). */
async function expectNoSideScroll(page: Page, screen: string) {
  const { scroll, client } = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(scroll, `${screen}: the page is ${scroll}px wide in a ${client}px window`).toBeLessThanOrEqual(client);
}

/** Press Tab until `target` has focus (keyboard only); fail if it can't be reached. */
async function tabTo(page: Page, target: Locator, limit = 80) {
  await expect(target).toBeVisible();
  for (let i = 0; i < limit; i++) {
    if (await target.evaluate((el) => el === document.activeElement)) return;
    await page.keyboard.press("Tab");
  }
  throw new Error(`could not reach ${target} with Tab`);
}

/** The focused element shows a focus ring (outline or box-shadow) as :focus-visible. */
async function expectFocusRing(page: Page) {
  const ring = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement;
    const style = getComputedStyle(el);
    return {
      visible: el.matches(":focus-visible"),
      outline: style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0,
      shadow: style.boxShadow !== "none",
      what: `${el.tagName} ${el.getAttribute("aria-label") ?? el.textContent?.slice(0, 30)}`,
    };
  });
  expect(ring.visible, `${ring.what} matches :focus-visible`).toBe(true);
  expect(ring.outline || ring.shadow, `${ring.what} shows a focus ring`).toBe(true);
}

function libraryRoutes() {
  const total = LIBRARY_PAPERS.reduce((sum, p) => sum + p.passage_count, 0);
  return {
    "/api/papers": async (route: import("@playwright/test").Route) =>
      route.fulfill({ status: 200, headers: CORS, json: { papers: LIBRARY_PAPERS, total_passages: total } }),
  };
}

test("layout: no sideways scrolling on the Ask, Library and state screens", async ({ page }) => {
  await fakeBackend(page, { routes: libraryRoutes() });
  await page.goto("/");
  await askOnPage(page);
  await expect(page.getByText("All citations verified")).toBeVisible();
  await expectNoSideScroll(page, "Ask with an answer");
  await page.getByRole("button", { name: /^Citation 1: LoRA/ }).click();
  await expect(page.getByRole("dialog").locator(".react-pdf__Page canvas")).toBeVisible({ timeout: 15_000 });
  await expectNoSideScroll(page, "source viewer");
  await page.keyboard.press("Escape");

  await page.getByRole("link", { name: "Library" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("2 papers");
  await expectNoSideScroll(page, "Library");

  await page.unrouteAll({ behavior: "ignoreErrors" });
  await fakeBackend(page, {
    routes: libraryRoutes(),
    usage: { ...USAGE, used: 50, remaining: 0 },
    askEvents: [["error", { kind: "daily_limit", used: 50, limit: 50, resets_at: "2026-10-26T00:00:00Z" }]],
  });
  await page.goto("/");
  await askOnPage(page);
  await page.getByRole("button", { name: "Browse passages instead" }).click();
  await expect(page.getByRole("list", { name: /matching passages/i })).toBeVisible();
  await expectNoSideScroll(page, "daily limit with browsed passages");

  await page.unrouteAll({ behavior: "ignoreErrors" });
  await fakeBackend(page, { routes: libraryRoutes(), askEvents: [["answer", HELD_BACK_ANSWER]] });
  await page.goto("/");
  await askOnPage(page);
  await page.getByRole("button", { name: "View the unverified answer" }).click();
  await expectNoSideScroll(page, "held back with the unverified answer");
});

test("keyboard only: scope, ask, open a citation, library", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "phone", "at 375 px the scope is a sheet; the US4 phone run covers it");
  await fakeBackend(page, { routes: libraryRoutes() });
  await page.goto("/");

  // US4: clear a paper with Space.
  const attention = page.getByRole("checkbox", { name: /Attention/ });
  await tabTo(page, attention);
  await expectFocusRing(page);
  await page.keyboard.press("Space");
  await expect(attention).not.toBeChecked();
  await expect(page.getByRole("region", { name: "Search scope" })).toContainText("1 of 2 papers");

  // US1: type and send with Enter.
  await tabTo(page, page.getByRole("textbox", { name: /ask about your papers/i }));
  await page.keyboard.type("What is LoRA?");
  await page.keyboard.press("Enter");
  await expect(page.getByText("All citations verified")).toBeVisible();

  // US2: open a citation with Enter and with Space; Escape closes and returns focus.
  const chip = page.getByRole("button", { name: /^Citation 1: LoRA/ });
  await tabTo(page, chip);
  await expectFocusRing(page);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(chip).toBeFocused();
  await page.keyboard.press("Space");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(chip).toBeFocused();

  // US4: a new conversation.
  await tabTo(page, page.getByRole("button", { name: "New conversation" }));
  await expectFocusRing(page);
  await page.keyboard.press("Enter");
  await expect(chip).toHaveCount(0);

  // US3: to the Library, open and cancel a delete.
  const library = page.getByRole("link", { name: "Library" });
  await tabTo(page, library);
  await expectFocusRing(page);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("2 papers");
  const remove = page.getByRole("button", { name: /^Delete BERT/ });
  await tabTo(page, remove);
  await expectFocusRing(page);
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await tabTo(page, dialog.getByRole("button", { name: "Cancel" }), 10);
  await expectFocusRing(page);
  await page.keyboard.press("Enter");
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("heading", { name: /^BERT/ })).toBeVisible();
});

// --- Answer reveal timing and reduced motion (SC-011, FR-011) ---

/** In the page: ms since the answer event, the lowest opacity inside the answer, and whether
 *  the chips and the badge are there. */
function revealState() {
  const article = document.querySelector("article");
  if (!article) return null;
  const parts = [article, ...article.querySelectorAll<HTMLElement>("*")];
  let minOpacity = 1;
  for (const el of parts) {
    // Opacity multiplies down the tree; any ancestor below 1 hides part of the answer.
    minOpacity = Math.min(minOpacity, parseFloat(getComputedStyle(el).opacity));
  }
  return {
    elapsed: performance.now() - (window as unknown as { __answerAt: number }).__answerAt,
    minOpacity,
    chips: article.querySelectorAll("button[aria-label^='Citation']").length,
    badge: article.textContent?.includes("All citations verified") ?? false,
  };
}

const REVEAL_STEPS = [{ afterMs: 300, event: "answer", data: ANSWER }];

test("reveal: text, chips and badge are fully shown within 500 ms of the answer", async ({ page }) => {
  await streamAskInPage(page, REVEAL_STEPS);
  await fakeBackend(page);
  await page.goto("/");
  await askOnPage(page);
  const done = await page.waitForFunction(
    (fn) => {
      const state = (new Function(`return (${fn})()`))() as ReturnType<typeof revealState>;
      return state && state.minOpacity === 1 && state.chips > 0 && state.badge ? state : null;
    },
    revealState.toString(),
    { polling: "raf", timeout: 5_000 },
  );
  const state = (await done.jsonValue()) as NonNullable<ReturnType<typeof revealState>>;
  expect(state.chips).toBe(2); // the fixture answer cites [1] and [2]
  console.log(`answer fully revealed ${state.elapsed.toFixed(0)} ms after the answer event`);
  expect(state.elapsed, `fully revealed after ${state.elapsed.toFixed(0)} ms`).toBeLessThan(500);
});

test("reduced motion: the answer appears in one step", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await streamAskInPage(page, REVEAL_STEPS);
  await fakeBackend(page);
  await page.goto("/");
  await askOnPage(page);
  // The first frame that shows the answer at all must show all of it.
  const first = await page.waitForFunction(
    (fn) => (new Function(`return (${fn})()`))() as ReturnType<typeof revealState>,
    revealState.toString(),
    { polling: "raf", timeout: 5_000 },
  );
  const state = (await first.jsonValue()) as NonNullable<ReturnType<typeof revealState>>;
  expect(state.minOpacity).toBe(1);
  expect(state.chips).toBe(2); // the fixture answer cites [1] and [2]
  expect(state.badge).toBe(true);
});

// --- Feature 4: summaries ---

function summaryRoutes(saved: boolean) {
  return {
    "/api/papers": async (route: import("@playwright/test").Route) =>
      route.fulfill({ status: 200, headers: CORS, json: { papers: [LORA_CARD], total_passages: 56 } }),
    "/api/summaries": async (route: import("@playwright/test").Route) =>
      route.fulfill({ status: 200, headers: CORS, json: { plan: { max_requests: 6 }, papers: [
        { paper_id: "lora", title: LORA_CARD.title, arxiv_id: LORA_CARD.arxiv_id,
          summary: saved ? { status: "current", created_at: LORA_SUMMARY.created_at, model: LORA_SUMMARY.model }
            : { status: "none", created_at: null, model: null } },
      ] } }),
    "/api/summaries/lora": async (route: import("@playwright/test").Route) =>
      saved
        ? route.fulfill({ status: 200, headers: CORS, json: LORA_SUMMARY })
        : route.fulfill({ status: 404, headers: CORS, json: { kind: "not_saved", plan: { max_requests: 6 } } }),
  };
}

test("F4 US1 summary", async ({ page }) => {
  await streamPostInPage(page, "/api/summaries/lora", SUMMARY_STEPS);
  await fakeBackend(page, { routes: summaryRoutes(false) });
  await page.goto("/library");
  await page.getByRole("article").getByRole("link", { name: "Summarize" }).click(); // the card, not the tab
  await expect(page).toHaveURL(/\/summarize\/lora$/, { timeout: 30_000 }); // a first visit compiles the route
  await expect(page.getByText("uses 6 requests · 16 left today")).toBeVisible();
  await page.getByRole("button", { name: "Summarize this paper" }).click();

  // Progress per part, then the checked parts.
  await expect(page.getByText("Writing method")).toBeVisible();
  await expect(page.getByText(/LoRA freezes the pretrained model/)).toBeVisible();
  const headings = page.getByRole("heading", { level: 2 });
  await expect(headings).toHaveText(["Problem", "Method", "Data", "Results", "Limitations"]);
  await expect(page.getByText("All citations verified")).toBeVisible();

  // A citation opens the PDF at the passage with its highlight.
  await page.getByRole("region", { name: "Method" }).getByRole("button", { name: /^Citation 1:/ }).click();
  const viewer = page.getByRole("dialog");
  await expect(viewer.locator(".react-pdf__Page canvas")).toBeVisible({ timeout: 15_000 });
  await expect(viewer.getByRole("img", { name: /highlighted passage/i })).toBeVisible();
});
