import type { Page } from "@playwright/test";

import { addDays } from "./lib/dates";
import { genFixture } from "./lib/htgen";
import { newUser } from "./lib/users";
import { expect, test } from "./test";

// SPEC §8 stage 12, scenario 3 (§9 #8): the same file uploaded again changes nothing — the report
// has 0 new records, all of them duplicates, and the summaries stay the same.

const COLUMNS = ["file", "uploaded", "status", "total", "new", "duplicate", "conflict", "invalid"] as const;

// The rows of «История загрузок», newest first, as numbers where the column is a count.
async function historyRows(page: Page) {
  const rows = page.getByRole("table", { name: "История загрузок" }).locator("tbody > tr");
  const result = [];
  for (const row of await rows.all()) {
    const cells = await row.locator("td").allInnerTexts();
    const entry = Object.fromEntries(COLUMNS.map((column, i) => [column, cells[i]?.trim() ?? ""]));
    const count = (column: (typeof COLUMNS)[number]) => Number(entry[column].replace(/\D/g, ""));
    result.push({
      file: entry.file,
      status: entry.status,
      total: count("total"),
      new: count("new"),
      duplicate: count("duplicate"),
      conflict: count("conflict"),
      invalid: count("invalid"),
    });
  }
  return result;
}

async function uploadInUi(page: Page, file: string, expectedRows: number) {
  await page.getByLabel("Выберите файл NDJSON").setInputFiles(file);
  const table = page.getByRole("table", { name: "История загрузок" });
  await expect(table.locator("tbody > tr")).toHaveCount(expectedRows);
  await expect(table.locator("tbody > tr").first()).toContainText("Готово", { timeout: 60_000 });
}

test("повторная загрузка того же файла: 0 новых, итоги те же", async ({ page }) => {
  const user = await newUser(page);
  const from = addDays(user.today, -3);
  const to = addDays(user.today, -1);
  const file = genFixture({ end: to, days: 3, seed: 31 });
  const range = `/api/summary/range?from=${from}&to=${to}`;
  const steps = page.getByRole("region", { name: "Шаги", exact: true });

  await page.goto("/upload");
  await uploadInUi(page, file, 1);
  const [first] = await historyRows(page);
  expect(first.new).toBeGreaterThan(0);
  expect(first.new).toBe(first.total);

  const before = await (await page.request.get(range)).json();
  await page.goto(`/?date=${to}`);
  // The card's text as toHaveText reads it (textContent): value, difference and goal.
  await expect(steps).toContainText(/\d/);
  const stepsBefore = (await steps.textContent()) ?? "";

  await page.goto("/upload");
  await uploadInUi(page, file, 2);
  const [again] = await historyRows(page);
  expect(again).toMatchObject({ status: "Готово", total: first.total, new: 0, conflict: 0, invalid: 0 });
  expect(again.duplicate).toBe(first.total);

  // Totals of every day are the same as after the first upload.
  expect(await (await page.request.get(range)).json()).toEqual(before);
  await page.goto(`/?date=${to}`);
  await expect(steps).toHaveText(stepsBefore);
});
