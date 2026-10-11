import { test as base, expect } from "@playwright/test";

import { clockOf, type Clock } from "./lib/clock";
import { CSRF_HEADERS } from "./lib/env";

// `test` of the scenarios: the automatic `clock` fixture checks that the server's Clock starts at
// real time and puts it back to 0 after every test, whatever the test did (CLAUDE.md §5, "Dev clock").
export const test = base.extend<{ clock: Clock; rulesOffAfter: boolean; rulesOff: void }>({
  clock: [
    async ({ request }, use) => {
      const clock = clockOf(request);
      expect((await clock.get()).offset_seconds, "the dev Clock was left shifted").toBe(0);
      try {
        await use(clock);
      } finally {
        await clock.set(0);
      }
    },
    { auto: true },
  ],
  // `test.use({ rulesOffAfter: true })` (scenarios 6–8): after the test, all rules of the user logged
  // in in the test's browser context are turned off. Their data lie ahead of real time; once the
  // Clock is back at 0, the worker would evaluate the rules by the real today, open them again and
  // send the letter on the next run's Clock shift. Torn down before `clock` (it depends on it).
  rulesOffAfter: [false, { option: true }],
  rulesOff: [
    async ({ context, clock: _clock, rulesOffAfter }, use) => {
      await use();
      if (!rulesOffAfter) return;
      const response = await context.request.get("/api/rules");
      if (response.status() === 401) return; // the test never logged in
      expect(response.status(), await response.text()).toBe(200);
      for (const rule of (await response.json()) as { code: string; enabled: boolean }[]) {
        if (!rule.enabled) continue;
        const patched = await context.request.patch(`/api/rules/${rule.code}`, {
          data: { enabled: false },
          headers: CSRF_HEADERS,
        });
        expect(patched.status(), await patched.text()).toBe(200);
      }
    },
    { auto: true },
  ],
});

export { expect };
