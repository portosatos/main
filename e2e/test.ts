import { test as base, expect } from "@playwright/test";

import { clockOf, type Clock } from "./lib/clock";

// `test` of the scenarios: the automatic `clock` fixture checks that the server's Clock starts at
// real time and puts it back to 0 after every test, whatever the test did (CLAUDE.md §5, "Dev clock").
export const test = base.extend<{ clock: Clock }>({
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
});

export { expect };
