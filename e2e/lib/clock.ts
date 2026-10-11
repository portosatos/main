import { expect, type APIRequestContext } from "@playwright/test";

import { CSRF_HEADERS } from "./env";

export type ClockState = { offset_seconds: number; system_now: string; now: string };

export type Clock = {
  get(): Promise<ClockState>;
  // Shifts the server's Clock (`/api/dev/clock`, only APP_ENV=dev); 0 — real time.
  set(offsetSeconds: number): Promise<ClockState>;
  // Moves the Clock `seconds` further from where it is now.
  advance(seconds: number): Promise<ClockState>;
  // Moves the Clock forward to the next HH:MM of the users' zone (TIMEZONE), so scenarios with
  // letters do not depend on the time of day they run at (midnight, quiet hours).
  toLocal(hhmm: string): Promise<ClockState>;
};

export function clockOf(request: APIRequestContext): Clock {
  const clock: Clock = {
    async get() {
      const response = await request.get("/api/dev/clock");
      expect(response.status(), "GET /api/dev/clock: is the stack in APP_ENV=dev?").toBe(200);
      return (await response.json()) as ClockState;
    },
    async set(offsetSeconds) {
      const response = await request.post("/api/dev/clock", {
        data: { offset_seconds: offsetSeconds },
        headers: CSRF_HEADERS,
      });
      expect(response.status(), await response.text()).toBe(200);
      return (await response.json()) as ClockState;
    },
    async advance() {
      throw new Error("step 12.2: not implemented");
    },
    async toLocal() {
      throw new Error("step 12.2: not implemented");
    },
  };
  return clock;
}
