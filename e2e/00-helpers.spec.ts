import { readFileSync } from "node:fs";

import { digests, recommendations, setGoals, setRule } from "./lib/account";
import { addDays, localDate, localTime } from "./lib/dates";
import { genFixture } from "./lib/htgen";
import { mailpit } from "./lib/mailpit";
import { CSRF_HEADERS } from "./lib/env";
import { newUser, PASSWORD, uniqueEmail } from "./lib/users";
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

// Helpers of step 12.2.

test("localDate and localTime are in the users' zone", () => {
  // Moscow is UTC+3.
  expect(localDate("2026-10-11T21:30:00Z")).toBe("2026-10-12");
  expect(localTime("2026-10-11T21:30:00Z")).toBe("00:30");
  expect(localTime(new Date("2026-10-11T08:05:59Z"))).toBe("11:05");
});

test("clock.toLocal moves forward to the next HH:MM of the zone, clock.advance adds to it", async ({ clock }) => {
  const noon = await clock.toLocal("12:00");
  expect(localTime(noon.now)).toBe("12:00");
  expect(noon.offset_seconds).toBeGreaterThan(0);
  expect(noon.offset_seconds).toBeLessThanOrEqual(86_400);
  const later = await clock.advance(90);
  expect(later.offset_seconds).toBe(noon.offset_seconds + 90);
});

test("the account helpers read and change the session user's data", async ({ page }) => {
  const user = await newUser(page);
  expect(await recommendations(page)).toEqual([]);
  expect(await digests(page)).toMatchObject({ notify_email: user.email, pending: 0, items: [] });
  await setGoals(page, { steps: 1234, sleep: 7.5 });
  const goals = (await (await page.request.get("/api/goals")).json()) as { kind: string; target: number }[];
  expect(goals.map((goal) => [goal.kind, goal.target])).toEqual([
    ["steps", 1234],
    ["sleep", 7.5],
  ]);
  await setRule(page, "R3", false);
  const rules = (await (await page.request.get("/api/rules")).json()) as { code: string; enabled: boolean }[];
  expect(rules.find((rule) => rule.code === "R3")?.enabled).toBe(false);
});

// rulesOffAfter (e2e/test.ts): the user of a test with the option has every rule off afterwards.
let ruledUser = "";

test.describe("with rulesOffAfter", () => {
  test.use({ rulesOffAfter: true });

  test("a test with rulesOffAfter starts with its rules on", async ({ page }) => {
    ruledUser = (await newUser(page)).email;
    const rules = (await (await page.request.get("/api/rules")).json()) as { enabled: boolean }[];
    expect(rules.length).toBeGreaterThan(0);
    expect(rules.every((rule) => rule.enabled)).toBe(true);
  });
});

test("after it, the rules of its user are off", async ({ page }) => {
  expect(ruledUser, "the previous test registers the user").not.toBe("");
  const login = await page.request.post("/api/auth/login", {
    data: { email: ruledUser, password: PASSWORD },
    headers: CSRF_HEADERS,
  });
  expect(login.status(), await login.text()).toBe(200);
  const rules = (await (await page.request.get("/api/rules")).json()) as { code: string; enabled: boolean }[];
  expect(rules.filter((rule) => rule.enabled)).toEqual([]);
});
