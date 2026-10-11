import { readFileSync } from "node:fs";

import { addDays } from "./lib/dates";
import { genFixture } from "./lib/htgen";
import { mailpit } from "./lib/mailpit";
import { newUser, uniqueEmail } from "./lib/users";
import { expect, test } from "./test";

// The helpers of the scenarios themselves (beyond the plan): a broken helper should fail here with
// a plain message, not somewhere inside a scenario.

test("newUser registers a fresh user and logs the page in", async ({ page }) => {
  const user = await newUser(page);
  expect(user.today).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  await page.goto("/");
  await expect(page.getByRole("banner")).toContainText(user.email);
  expect(uniqueEmail()).not.toBe(uniqueEmail());
});

test("clock.set shifts the server's Clock", async ({ clock }) => {
  const before = await clock.get();
  const shifted = await clock.set(86_400);
  expect(shifted.offset_seconds).toBe(86_400);
  expect(Date.parse(shifted.now) - Date.parse(before.now)).toBeGreaterThan(86_000_000);
  // The fixture puts it back to 0; the next test starts by checking that.
});

test("the next test starts with the Clock at real time", async ({ clock }) => {
  expect((await clock.get()).offset_seconds).toBe(0);
});

test("genFixture writes the requested period with htgen", async () => {
  const file = genFixture({ end: "2026-10-07", days: 2, seed: 1 });
  const lines = readFileSync(file, "utf8").trimEnd().split("\n");
  expect(JSON.parse(lines[0]).type).toBe("meta");
  const dates = new Set(lines.slice(1).map((line) => JSON.parse(line).start?.slice(0, 10)));
  expect(dates).toContain(addDays("2026-10-07", -1));
  expect(dates).toContain("2026-10-07");
  expect(dates).not.toContain("2026-10-08");
});

test("mailpit.messages lists nothing for a fresh address", async () => {
  expect(await mailpit.messages(uniqueEmail())).toEqual([]);
});
