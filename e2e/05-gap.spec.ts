import { addDays } from "./lib/dates";
import { genFixture } from "./lib/htgen";
import { uploadAndWait } from "./lib/ingest";
import { newUser } from "./lib/users";
import { expect, test } from "./test";

// SPEC §8 stage 12, scenario 5 (§9 #9, F6): a day that no device covered is «нет данных» —
// not 0 steps and not 0 sleep — and a hatched column on the charts.

test.fail();

const CARDS = ["Сон", "Шаги", "Активные минуты", "Пульс в покое", "Пиковый пульс"];

test("день с пропуском показан как «нет данных»", async ({ page }) => {
  const user = await newUser(page);
  const end = addDays(user.today, -1);
  const gap = addDays(user.today, -3);
  // Five days, the whole local date `gap` without any device (htgen --gap without @device).
  const file = genFixture({
    end,
    days: 5,
    seed: 51,
    gaps: [`${gap}T00:00/${addDays(gap, 1)}T00:00`],
  });
  await uploadAndWait(page, file);

  await page.goto(`/?date=${gap}`);
  await expect(page.getByText("За этот день данных нет.")).toBeVisible();
  for (const title of CARDS) {
    const card = page.getByRole("region", { name: title, exact: true });
    await expect(card.getByText("нет данных", { exact: true })).toBeVisible();
    // Not a zero in place of the missing value.
    await expect(card.getByText(/^0(\s|$)/)).toHaveCount(0);
  }

  // The neighbours have data, so the gap is exactly that date.
  for (const date of [addDays(gap, -1), addDays(gap, 1)]) {
    await page.goto(`/?date=${date}`);
    await expect(page.getByRole("region", { name: "Шаги", exact: true }).getByText(/^\d[\d\s]*$/)).toBeVisible();
  }

  // The week before gap+1 on the charts: three days before the file and the gap are hatched,
  // the other three days are bars.
  await page.goto(`/?date=${addDays(gap, 1)}`);
  for (const chart of ["Шаги по дням", "Сон по дням"]) {
    const figure = page.getByRole("figure", { name: chart });
    await expect(figure.locator('[data-gap="no_data"]')).toHaveCount(4);
  }
});
