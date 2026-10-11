import { expect, type Page } from "@playwright/test";

import { CSRF_HEADERS } from "./env";

// The user's settings, goals, rules, recommendations and digests through the API of the page's
// session (docs/API.md), for the steps of a scenario that are not what it checks.

export type RecommendationStatus = "open" | "resolved" | "closed_rule_disabled";

export type Recommendation = {
  id: string;
  rule_code: string;
  status: RecommendationStatus;
  anchor_date: string;
  resolve_reason: string | null;
};

export type Digest = {
  status: "planned" | "sent";
  local_date: string;
  planned_at: string;
  plan_reason: "window" | "max_delay" | "daily_limit" | "quiet_hours";
  sent_at: string | null;
  subject: string | null;
  recommendations: number;
};

export type Digests = { notify_email: string | null; pending: number; items: Digest[] };

// `GET /api/recommendations`, newest first.
export async function recommendations(
  page: Page,
  query: { status?: RecommendationStatus[]; rule?: string } = {},
): Promise<Recommendation[]> {
  const params = new URLSearchParams();
  for (const status of query.status ?? []) params.append("status", status);
  if (query.rule) params.set("rule", query.rule);
  const response = await page.request.get(`/api/recommendations?${params}`);
  expect(response.status(), await response.text()).toBe(200);
  return (await response.json()) as Recommendation[];
}

// `PATCH /api/rules/{code}`.
export async function setRule(page: Page, code: string, enabled: boolean): Promise<void> {
  const response = await page.request.patch(`/api/rules/${code}`, { data: { enabled }, headers: CSRF_HEADERS });
  expect(response.status(), await response.text()).toBe(200);
}

// `PUT /api/goals`.
export async function setGoals(page: Page, goals: { steps: number; sleep: number }): Promise<void> {
  const response = await page.request.put("/api/goals", { data: goals, headers: CSRF_HEADERS });
  expect(response.status(), await response.text()).toBe(200);
}

// `GET /api/digests`: the planned digest first, then the sent ones, newest first.
export async function digests(page: Page): Promise<Digests> {
  const response = await page.request.get("/api/digests");
  expect(response.status(), await response.text()).toBe(200);
  return (await response.json()) as Digests;
}
