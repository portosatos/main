import { randomUUID } from "node:crypto";

import { expect, type Page } from "@playwright/test";

import { CSRF_HEADERS, TIMEZONE } from "./env";

export type User = {
  email: string;
  password: string;
  // The user's local date by the server's Clock (/api/auth/me).
  today: string;
};

export const PASSWORD = "e2e-pass-123";

// A fresh address per call: every scenario works on its own user (SPEC §8 stage 12).
export function uniqueEmail(prefix = "e2e"): string {
  return `${prefix}-${randomUUID().slice(0, 12)}@example.com`;
}

// Registers a fresh user through the API of the page's context, so the page is logged in.
export async function newUser(page: Page): Promise<User> {
  const email = uniqueEmail();
  const registered = await page.request.post("/api/auth/register", {
    data: { email, password: PASSWORD, timezone: TIMEZONE },
    headers: CSRF_HEADERS,
  });
  expect(registered.status(), await registered.text()).toBe(201);
  const me = await page.request.get("/api/auth/me");
  expect(me.status()).toBe(200);
  const { today } = (await me.json()) as { today: string };
  return { email, password: PASSWORD, today };
}
