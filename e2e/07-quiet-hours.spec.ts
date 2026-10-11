import { digests, recommendations } from "./lib/account";
import { addDays, localDate, localTime } from "./lib/dates";
import { DIGEST_TICK_MS } from "./lib/env";
import { genFixture } from "./lib/htgen";
import { uploadAndWait } from "./lib/ingest";
import { mailpit } from "./lib/mailpit";
import { newUser } from "./lib/users";
import { expect, test } from "./test";

// SPEC §8 stage 12, scenario 7 (§9 #15, F10): a digest that falls into quiet hours waits for their
// end — no letter while they last, the letter right after.

test.fail();

test("тихие часы: письма нет, после их окончания приходит", async ({ page, clock }) => {
  test.setTimeout(180_000);
  await clock.toLocal("12:00");
  const user = await newUser(page);

  // Quiet hours 11:00–13:00 around the Clock's midday, set on the settings page.
  await page.goto("/settings");
  // The form is filled from the server first; edits made before that would be reset.
  await expect(page.getByLabel("Почта для писем")).toHaveValue(user.email);
  await page.getByLabel("Тихие часы", { exact: true }).check();
  await page.getByLabel("Начало").fill("11:00");
  await page.getByLabel("Конец").fill("13:00");
  await page.getByRole("button", { name: "Сохранить" }).click();
  await expect(page.getByText("Настройки сохранены")).toBeVisible();

  const shortSleep = genFixture({ end: addDays(user.today, -1), days: 4, seed: 71, scenario: "short-sleep" });
  await uploadAndWait(page, shortSleep);
  expect(await recommendations(page, { status: ["open"], rule: "R1" })).toHaveLength(1);

  // The window would send it at ~12:01; quiet hours move it to their end, 13:00 the same day.
  const nextLetter = page.getByRole("region", { name: "Ближайшее письмо" });
  await expect(nextLetter).toContainText("тихие часы", { timeout: 3 * DIGEST_TICK_MS });
  const [planned] = (await digests(page)).items;
  expect(planned).toMatchObject({ status: "planned", plan_reason: "quiet_hours", local_date: user.today });
  expect(localTime(planned.planned_at)).toBe("13:00");

  // Half an hour later the window is long over, but it is still quiet: no letter.
  await clock.advance(30 * 60);
  await page.waitForTimeout(2 * DIGEST_TICK_MS);
  expect(await mailpit.messages(user.email)).toHaveLength(0);

  // After the end of quiet hours the letter comes, dated after 13:00 of the same day.
  await clock.toLocal("13:01");
  const [sent] = await mailpit.waitFor(user.email, 1, 4 * DIGEST_TICK_MS);
  const letter = await mailpit.message(sent.ID);
  expect(localDate(letter.Date)).toBe(user.today);
  expect(localTime(letter.Date) >= "13:00").toBe(true);
  expect(letter.Text).toContain("Недосып");
});
