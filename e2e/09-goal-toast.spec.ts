import { setGoals } from "./lib/account";
import { addDays } from "./lib/dates";
import { genFixture } from "./lib/htgen";
import { uploadAndWait } from "./lib/ingest";
import { newUser } from "./lib/users";
import { expect, test } from "./test";

// SPEC §8 stage 12, scenario 9 (§9 #11, F8): a goal met shows a toast in the open tab at once —
// for today and yesterday; an older date of the same import goes to the bell without a toast.

test("цель достигнута → тост", async ({ page, clock }) => {
  const user = await newUser(page);
  // Goals have a history: a past date is judged by the goal in effect then. Set three days ago,
  // 1000 steps are met by any day of htgen and 16 h of sleep never, so only steps toasts come.
  await clock.set(-3 * 86_400);
  await setGoals(page, { steps: 1000, sleep: 16 });
  await clock.set(0);

  // The dashboard with its event stream open, before the upload.
  const stream = page.waitForResponse((response) => response.url().endsWith("/api/events"));
  await page.goto("/");
  await stream;

  await uploadAndWait(page, genFixture({ end: user.today, days: 3, seed: 91 }));
  await expect(page.getByText("Цель по шагам на сегодня выполнена")).toBeVisible();
  await expect(page.getByText("Цель по шагам на вчера выполнена")).toBeVisible();

  // The day before yesterday: in the bell, not a toast; no sleep goal met.
  const response = await page.request.get("/api/notifications");
  expect(response.status()).toBe(200);
  const { items } = (await response.json()) as {
    items: { type: string; payload: { kind: string; local_date: string } }[];
  };
  const achieved = items
    .filter((notification) => notification.type === "goal.achieved")
    .map(({ payload }) => `${payload.kind} ${payload.local_date}`);
  const days = [addDays(user.today, -2), addDays(user.today, -1), user.today];
  expect(achieved.sort()).toEqual(days.map((day) => `steps ${day}`));
  await expect(page.getByText(/^Цель по шагам на (?!сегодня|вчера)/)).toHaveCount(0);
  await expect(page.getByText(/^Цель по сну/)).toHaveCount(0);
});
