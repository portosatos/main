import type { APIRequestContext } from "@playwright/test";

export type ClockState = { offset_seconds: number; system_now: string; now: string };

export type Clock = {
  get(): Promise<ClockState>;
  // Shifts the server's Clock (`/api/dev/clock`, only APP_ENV=dev); 0 — real time.
  set(offsetSeconds: number): Promise<ClockState>;
};

export function clockOf(request: APIRequestContext): Clock {
  void request;
  throw new Error("step 12.1: not implemented");
}
