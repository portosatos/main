import type { Page } from "@playwright/test";

import { recommendations } from "./lib/account";
import { addDays } from "./lib/dates";
import { genFixture } from "./lib/htgen";
import { uploadAndWait } from "./lib/ingest";
import { newUser } from "./lib/users";
import { expect, test } from "./test";

// SPEC §8 stage 12, scenario 10 (§9 #12, F9): a rule turned off is not evaluated — the data that
// opens it opens nothing; turned on, it opens; turned off again, its recommendation goes to the
// history as «правило отключено» and stays there.

test.fail();

async function switchR1(page: Page, enabled: boolean) {
  await page.goto("/rules");
  const r1 = page.getByRole("switch", { name: "Правило R1 включено" });
  await expect(r1).toHaveAttribute("aria-checked", String(!enabled));
  await r1.click();
  await expect(r1).toHaveAttribute("aria-checked", String(enabled));
}

test("отключённое правило не срабатывает, история видна", async ({ page }) => {
  const user = await newUser(page);
  const shortSleep = genFixture({ end: addDays(user.today, -1), days: 4, seed: 101, scenario: "short-sleep" });
  const r1 = page.getByRole("article", { name: /^R1 Недосып/ });

  // Off before the data: three short nights open nothing.
  await switchR1(page, false);
  await uploadAndWait(page, shortSleep);
  expect(await recommendations(page, { rule: "R1" })).toEqual([]);
  await page.goto("/recommendations");
  await expect(page.getByText("Активных рекомендаций нет.")).toBeVisible();

  // On: evaluated at once on the same data, R1 opens.
  await switchR1(page, true);
  await page.goto("/recommendations");
  await expect(r1).toContainText("активна");

  // Off again: R1 leaves «Активные» for «История» with the reason, the filter by rule finds it.
  await switchR1(page, false);
  await page.goto("/recommendations");
  await expect(page.getByText("Активных рекомендаций нет.")).toBeVisible();
  await page.getByRole("tab", { name: "История" }).click();
  await page.getByLabel("Правило").selectOption("R1");
  await expect(r1).toHaveCount(1);
  await expect(r1).toContainText("правило отключено");

  // A new upload evaluates the rules again: R1 stays off, its history stays.
  // One more day before the same nights (htgen: the same records where the periods overlap).
  const longer = genFixture({ end: addDays(user.today, -1), days: 5, seed: 101, scenario: "short-sleep" });
  expect((await uploadAndWait(page, longer)).counts.new).toBeGreaterThan(0);
  const all = await recommendations(page, { rule: "R1" });
  expect(all.map((rec) => rec.status)).toEqual(["closed_rule_disabled"]);
  await page.reload();
  await page.getByRole("tab", { name: "История" }).click();
  await page.getByLabel("Правило").selectOption("R1");
  await expect(r1).toHaveCount(1);
  await expect(r1).toContainText("правило отключено");
});
