import type { Page } from "@playwright/test";

export type User = {
  email: string;
  password: string;
  // The user's local date by the server's Clock (/api/auth/me).
  today: string;
};

export const PASSWORD = "e2e-pass-123";

// A fresh address per call: every scenario works on its own user (SPEC §8 stage 12).
export function uniqueEmail(prefix = "e2e"): string {
  void prefix;
  throw new Error("step 12.1: not implemented");
}

// Registers a fresh user through the API of the page's context, so the page is logged in.
export async function newUser(page: Page): Promise<User> {
  void page;
  throw new Error("step 12.1: not implemented");
}
