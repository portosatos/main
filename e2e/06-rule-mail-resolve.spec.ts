import { digests, recommendations } from "./lib/account";
import { addDays } from "./lib/dates";
import { BASE_URL, DIGEST_TICK_MS } from "./lib/env";
import { genFixture } from "./lib/htgen";
import { uploadAndWait } from "./lib/ingest";
import { mailpit } from "./lib/mailpit";
import { newUser } from "./lib/users";
import { expect, test } from "./test";

// SPEC §8 stage 12, scenario 6 (§9 #13, F9, F10): `short-sleep` opens R1, it is on the
// recommendations page, its digest comes to Mailpit after the window (1 min in the e2e stack),
// and the `recovery` night closes R1 by itself — without a second letter.

// The user's data lie ahead of real time: its rules go off after the test (e2e/test.ts).
test.use({ rulesOffAfter: true });

test("short-sleep → R1 в интерфейсе → письмо в Mailpit → recovery → рекомендация закрыта", async ({
  page,
  clock,
}) => {
  // Waits for the real 1-minute window of the digest.
  test.setTimeout(240_000);
  // Midday of the users' zone: the letter is not moved by midnight or quiet hours.
  await clock.toLocal("12:00");
  const user = await newUser(page);

  await page.goto("/recommendations");
  await expect(page.getByText("Активных рекомендаций нет.")).toBeVisible();
  // Three short nights up to yesterday: R1 opens at the end of the job (docs/DATA_FORMAT.md).
  const shortSleep = genFixture({ end: addDays(user.today, -1), days: 4, seed: 61, scenario: "short-sleep" });
  await uploadAndWait(page, shortSleep);

  const r1 = page.getByRole("article", { name: /^R1 Недосып/ });
  await expect(r1).toBeVisible();
  await expect(r1).toContainText("активна");

  // The digest is planned by the window, then the letter comes.
  await expect
    .poll(async () => (await digests(page)).items.find((digest) => digest.status === "planned")?.plan_reason, {
      timeout: 3 * DIGEST_TICK_MS,
    })
    .toBe("window");
  const [sent] = await mailpit.waitFor(user.email, 1, 60_000 + 6 * DIGEST_TICK_MS);
  expect(sent.Subject).toBe("Трекер здоровья: 1 новая рекомендация");
  const letter = await mailpit.message(sent.ID);
  expect(letter.Text).toContain("Недосып");
  expect(letter.Text).toContain(`${BASE_URL}/recommendations`);
  expect(letter.HTML).toContain("<strong>Недосып</strong>");

  // The night ending today is 7.5–8.5 h: R1 closes by itself.
  await uploadAndWait(page, genFixture({ end: user.today, days: 1, seed: 62, scenario: "recovery" }));
  await expect(page.getByText("Активных рекомендаций нет.")).toBeVisible();
  await page.getByRole("tab", { name: "История" }).click();
  await expect(r1).toContainText("закрыта автоматически");
  const [closed] = await recommendations(page, { rule: "R1" });
  expect(closed).toMatchObject({ status: "resolved", resolve_reason: "auto" });

  // No letter about the closing (SPEC F9).
  await page.waitForTimeout(2 * DIGEST_TICK_MS);
  expect(await mailpit.messages(user.email)).toHaveLength(1);
});
