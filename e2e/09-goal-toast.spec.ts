import { setGoals } from "./lib/account";
import { addDays } from "./lib/dates";
import { genFixture } from "./lib/htgen";
import { uploadAndWait } from "./lib/ingest";
import { newUser } from "./lib/users";
import { expect, test } from "./test";

// SPEC §8 stage 12, scenario 9 (§9 #11, F8): a goal met shows a toast in the open tab at once —
// for today and yesterday; an older date of the same import goes to the bell without a toast.

test.fail();

test("цель достигнута → тост", async ({ page }) => {
  const user = await newUser(page);
  // Any day of htgen meets 1000 steps; 16 h of sleep is never met, so only the steps toasts come.
  await setGoals(page, { steps: 1000, sleep: 16 });

  // The dashboard with its event stream open, before the upload.
  const stream = page.waitForResponse((response) => response.url().endsWith("/api/events"));
  await page.goto("/");
  await stream;

  await uploadAndWait(page, genFixture({ end: user.today, days: 3, seed: 91 }));
  await expect(page.getByText("Цель по шагам на сегодня выполнена")).toBeVisible();
  await expect(page.getByText("Цель по шагам на вчера выполнена")).toBeVisible();
  await expect(page.getByText(/Цель по сну/)).toHaveCount(0);

  // The day before yesterday: in the bell, not a toast.
  await expect(page.getByText(/^Цель по шагам на (?!сегодня|вчера)/)).toHaveCount(0);
  const response = await page.request.get("/api/notifications");
  expect(response.status()).toBe(200);
  const { items } = (await response.json()) as { items: { type: string; payload: { local_date: string } }[] };
  const dates = items.filter((n) => n.type === "goal.achieved").map((n) => n.payload.local_date);
  expect(dates.sort()).toEqual([addDays(user.today, -2), addDays(user.today, -1), user.today]);
});
