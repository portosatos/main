import { digests, recommendations, setRule } from "./lib/account";
import { addDays, localDate, localTime } from "./lib/dates";
import { DIGEST_TICK_MS } from "./lib/env";
import { genFixture } from "./lib/htgen";
import { uploadAndWait } from "./lib/ingest";
import { mailpit } from "./lib/mailpit";
import { newUser } from "./lib/users";
import { expect, test } from "./test";

// SPEC §8 stage 12, scenario 8 (§9 #14, F10): one digest per local day. A rule that opens after
// the day's letter waits for the next day; moving the Clock there brings the second letter; Mailpit
// never has two letters of one local day.

test("лимит дайджестов: второе срабатывание в те же сутки без письма, на следующие сутки — второе письмо", async ({
  page,
  clock,
}) => {
  test.setTimeout(180_000);
  await clock.toLocal("12:00");
  const user = await newUser(page);

  // Short nights and few steps; R2 (few steps) is off for now, it is the second rule of the day.
  await setRule(page, "R2", false);
  const file = genFixture({ end: addDays(user.today, -1), days: 6, seed: 81, scenario: "short-sleep,sedentary" });
  await uploadAndWait(page, file);
  expect(await recommendations(page, { status: ["open"], rule: "R1" })).toHaveLength(1);

  // The first letter of the day: past the 1-minute window it goes within a tick.
  await clock.advance(2 * 60);
  const [first] = await mailpit.waitFor(user.email, 1, 4 * DIGEST_TICK_MS);
  const firstLetter = await mailpit.message(first.ID);
  expect(localDate(firstLetter.Date)).toBe(user.today);
  expect(firstLetter.Text).toContain("Недосып");
  expect(firstLetter.Text).not.toContain("Мало шагов");

  // R2 turned on is evaluated at once and opens the same day: its digest waits for 00:00 tomorrow.
  await page.goto("/rules");
  const r2 = page.getByRole("switch", { name: "Правило R2 включено" });
  await expect(r2).toHaveAttribute("aria-checked", "false");
  await r2.click();
  await expect(r2).toHaveAttribute("aria-checked", "true");
  await page.goto("/recommendations");
  await expect(page.getByRole("article", { name: /^R2 Мало шагов/ })).toBeVisible();
  await expect
    .poll(async () => (await digests(page)).items.find((digest) => digest.status === "planned")?.plan_reason, {
      timeout: 3 * DIGEST_TICK_MS,
    })
    .toBe("daily_limit");
  const planned = (await digests(page)).items.find((digest) => digest.status === "planned")!;
  expect(planned.local_date).toBe(addDays(user.today, 1));
  expect(localTime(planned.planned_at)).toBe("00:00");

  // Past its window the same day: still one letter.
  await clock.advance(2 * 60);
  await page.waitForTimeout(2 * DIGEST_TICK_MS);
  expect(await mailpit.messages(user.email)).toHaveLength(1);

  // The next local day: the second letter, with R2 only.
  await clock.toLocal("00:01");
  const [second] = await mailpit.waitFor(user.email, 2, 4 * DIGEST_TICK_MS);
  const secondLetter = await mailpit.message(second.ID);
  expect(localDate(secondLetter.Date)).toBe(addDays(user.today, 1));
  expect(secondLetter.Text).toContain("Мало шагов");
  expect(secondLetter.Text).not.toContain("Недосып");

  // Not more than one letter of a local day in Mailpit, and the digests agree.
  const letters = await Promise.all((await mailpit.messages(user.email)).map((m) => mailpit.message(m.ID)));
  const days = letters.map((letter) => localDate(letter.Date)).sort();
  expect(days).toEqual([user.today, addDays(user.today, 1)]);
  const sent = (await digests(page)).items.filter((digest) => digest.status === "sent");
  expect(sent.map((digest) => digest.local_date).sort()).toEqual(days);
});
