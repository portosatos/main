import { addDays } from "./lib/dates";
import { genFixture } from "./lib/htgen";
import { newUser } from "./lib/users";
import { expect, test } from "./test";

// SPEC §8 stage 12, scenario 4 (§9 #16, #19, F12): two tabs of one user (two pages of one context).
// An upload, a rule turned off and «Полезно» in the first tab show up in the second within 2 s.

// SPEC F12: a change in one tab appears in the other not later than in 2 seconds.
const TWO_SECONDS = 2_000;

test("две вкладки: загрузка, отключение правила и «Полезно» видны во второй ≤ 2 с", async ({
  page: first,
  context,
}) => {
  const user = await newUser(first);
  const second = await context.newPage();
  // Three short nights at the end: R1 opens when the file is processed (docs/DATA_FORMAT.md).
  const file = genFixture({ end: addDays(user.today, -1), days: 4, seed: 41, scenario: "short-sleep" });
  const fileName = file.split(/[\\/]/).pop()!;

  // Upload: the job appears and finishes in the second tab.
  await first.goto("/upload");
  await second.goto("/upload");
  await expect(second.getByText("Загрузок пока нет")).toBeVisible();
  await first.getByLabel("Выберите файл NDJSON").setInputFiles(file);
  await expect(first.getByText("Файл передан, идёт обработка.")).toBeVisible();
  const secondRow = second.getByRole("table", { name: "История загрузок" }).locator("tbody > tr").first();
  await expect(secondRow).toContainText(fileName, { timeout: TWO_SECONDS });
  const firstRow = first.getByRole("table", { name: "История загрузок" }).locator("tbody > tr").first();
  await expect(firstRow).toContainText("Готово", { timeout: 60_000 });
  await expect(secondRow).toContainText("Готово", { timeout: TWO_SECONDS });

  // A rule turned off in the first tab is off in the second.
  await first.goto("/rules");
  await second.goto("/rules");
  const rule = "Правило R5 включено";
  await expect(second.getByRole("switch", { name: rule })).toHaveAttribute("aria-checked", "true");
  await first.getByRole("switch", { name: rule }).click();
  await expect(second.getByRole("switch", { name: rule })).toHaveAttribute("aria-checked", "false", {
    timeout: TWO_SECONDS,
  });
  await expect(first.getByRole("switch", { name: rule })).toHaveAttribute("aria-checked", "false");

  // «Полезно» on R1 in the first tab is pressed in the second, and stays after a reload.
  await first.goto("/recommendations");
  await second.goto("/recommendations");
  const r1 = (page: typeof first) => page.getByRole("article", { name: /^R1 / });
  await expect(r1(first)).toBeVisible({ timeout: 30_000 });
  await expect(r1(second)).toBeVisible();
  const useful = (page: typeof first) => r1(page).getByRole("button", { name: "Полезно", exact: true });
  await expect(useful(second)).toHaveAttribute("aria-pressed", "false");
  await useful(first).click();
  await expect(useful(second)).toHaveAttribute("aria-pressed", "true", { timeout: TWO_SECONDS });
  await second.reload();
  await expect(useful(second)).toHaveAttribute("aria-pressed", "true");
});
