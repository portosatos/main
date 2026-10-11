import { mkdirSync } from "node:fs";
import path from "node:path";

import type { Page } from "@playwright/test";

import { digests, setGoals } from "./lib/account";
import { addDays } from "./lib/dates";
import { REPO_ROOT } from "./lib/env";
import { genFixture } from "./lib/htgen";
import { uploadAndWait } from "./lib/ingest";
import { newUser, type User } from "./lib/users";
import { expect, test } from "./test";

// SPEC §8 stage 13, §4 «Адаптивность»: screenshots of every page at 1280 and 375 px, and no
// horizontal scroll of the page at 375 px (a table or a chart may scroll inside its own box). The
// pages are shown to a fresh user with two weeks of data: a day without any device, short nights
// (R1 opens), goals. The screenshots go to docs/screenshots/ with `-u` (--update-snapshots):
//   cd e2e; npx playwright test screenshots.spec.ts -u
// Without it (scripts/e2e.*, CI) they go to the test's output in test-results/, so a run of the
// scenarios does not change docs/.

const DOCS_SHOTS_DIR = path.join(REPO_ROOT, "docs", "screenshots");
const WIDTHS = [1280, 375] as const;

type Shot = {
  name: string;
  // The address, from the user's `today`.
  path: (today: string) => string;
  heading: string;
  // Logged in (the user with data) or not.
  auth: boolean;
};

const PAGES: Shot[] = [
  { name: "login", path: () => "/login", heading: "Вход", auth: false },
  { name: "register", path: () => "/register", heading: "Регистрация", auth: false },
  { name: "dashboard-day", path: (today) => `/?date=${addDays(today, -1)}`, heading: "Дашборд", auth: true },
  { name: "dashboard-week", path: (today) => `/?view=week&date=${addDays(today, -1)}`, heading: "Дашборд", auth: true },
  { name: "upload", path: () => "/upload", heading: "Загрузка", auth: true },
  { name: "devices", path: () => "/devices", heading: "Устройства", auth: true },
  { name: "goals", path: () => "/goals", heading: "Цели", auth: true },
  { name: "recommendations", path: () => "/recommendations", heading: "Рекомендации", auth: true },
  { name: "rules", path: () => "/rules", heading: "Правила", auth: true },
  { name: "settings", path: () => "/settings", heading: "Настройки", auth: true },
];

// The user of the logged-in pages, made once for the file (one worker, see playwright.config.ts).
let user: User | undefined;
const storageState = path.join(REPO_ROOT, "e2e", "test-results", "screenshots-user.json");

test.beforeAll(async ({ browser }) => {
  // Not the storage state of the first test's describe: that file is written here.
  const context = await browser.newContext({ storageState: { cookies: [], origins: [] } });
  const page = await context.newPage();
  user = await newUser(page);
  const end = addDays(user.today, -1);
  // The gap lies before the three short nights: a night next to it is not valid, and R1 needs three.
  const gap = addDays(user.today, -6);
  const file = genFixture({
    end,
    days: 14,
    seed: 131,
    scenario: "short-sleep",
    gaps: [`${gap}T00:00/${addDays(gap, 1)}T00:00`],
  });
  await uploadAndWait(page, file);
  await setGoals(page, { steps: 8000, sleep: 7.5 });
  // R1 is open and its digest is in the queue of the dev panel: every logged-in page shows the
  // same panel, whenever its test runs (planned, then sent).
  await expect.poll(async () => (await digests(page)).items.length, { timeout: 15_000 }).toBeGreaterThan(0);
  await context.storageState({ path: storageState });
  await context.close();
});

// The page is shown once its heading is there and nothing is loading any more.
async function open(page: Page, shot: Shot): Promise<void> {
  await page.goto(shot.path(user!.today));
  await expect(page.getByRole("heading", { name: shot.heading, exact: true }).first()).toBeVisible();
  await expect(page.getByText("Загрузка…")).toHaveCount(0);
  await expect(page.locator(".animate-pulse")).toHaveCount(0);
  // The dev panel below the logged-in pages (APP_ENV=dev of the e2e stack) with its digest queue.
  if (shot.auth) await expect(page.getByText(/^Ждут письма: \d+/)).toBeVisible();
}

// Elements that stick out of the viewport on the right, for the failure message.
async function overflow(page: Page) {
  return page.evaluate(() => {
    const root = document.documentElement;
    const width = root.clientWidth;
    const culprits: string[] = [];
    for (const element of Array.from(document.body.querySelectorAll<HTMLElement>("*"))) {
      const right = element.getBoundingClientRect().right;
      if (right <= width + 0.5) continue;
      // Only the outermost of a nested group: its parent fits.
      const parent = element.parentElement;
      if (parent && parent !== document.body && parent.getBoundingClientRect().right > width + 0.5) continue;
      const classes = typeof element.className === "string" ? element.className.trim().split(/\s+/).slice(0, 4) : [];
      const text = (element.textContent ?? "").trim().replace(/\s+/g, " ").slice(0, 40);
      culprits.push(`${element.tagName.toLowerCase()}.${classes.join(".")} right=${Math.round(right)} «${text}»`);
    }
    return {
      scrollWidth: root.scrollWidth,
      clientWidth: width,
      // Hiding the overflow of the page would hide the problem, not fix it.
      overflowX: [getComputedStyle(root).overflowX, getComputedStyle(document.body).overflowX],
      culprits: culprits.slice(0, 10),
    };
  });
}

async function shoot(page: Page, shot: Shot, width: number): Promise<void> {
  const info = test.info();
  const update = info.config.updateSnapshots !== "missing" && info.config.updateSnapshots !== "none";
  const file = `${shot.name}-${width}.png`;
  if (update) mkdirSync(DOCS_SHOTS_DIR, { recursive: true });
  await page.screenshot({ path: update ? path.join(DOCS_SHOTS_DIR, file) : info.outputPath(file), fullPage: true });
}

for (const shot of PAGES) {
  test.describe(shot.name, () => {
    test.use({ storageState: shot.auth ? storageState : { cookies: [], origins: [] } });

    test(`no horizontal scroll at 375px: ${shot.name}`, async ({ page }) => {
      test.fail(shot.auth, "step 13.1: not implemented");
      await page.setViewportSize({ width: 375, height: 812 });
      await open(page, shot);
      const result = await overflow(page);
      expect(result.overflowX, "overflow-x of html and body").toEqual(["visible", "visible"]);
      expect(result.scrollWidth, `the page scrolls sideways, sticking out: ${result.culprits.join("; ")}`).toBeLessThanOrEqual(
        result.clientWidth,
      );
      await shoot(page, shot, 375);
    });

    test(`screenshot at 1280px: ${shot.name}`, async ({ page }) => {
      await page.setViewportSize({ width: WIDTHS[0], height: 800 });
      await open(page, shot);
      await shoot(page, shot, WIDTHS[0]);
    });
  });
}
