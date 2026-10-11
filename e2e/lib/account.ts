import type { Page } from "@playwright/test";

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
  _page: Page,
  _query: { status?: RecommendationStatus[]; rule?: string } = {},
): Promise<Recommendation[]> {
  throw new Error("step 12.2: not implemented");
}

// `PATCH /api/rules/{code}`.
export async function setRule(_page: Page, _code: string, _enabled: boolean): Promise<void> {
  throw new Error("step 12.2: not implemented");
}

// `PUT /api/goals`.
export async function setGoals(_page: Page, _goals: { steps: number; sleep: number }): Promise<void> {
  throw new Error("step 12.2: not implemented");
}

// `GET /api/digests`: the planned digest first, then the sent ones, newest first.
export async function digests(_page: Page): Promise<Digests> {
  throw new Error("step 12.2: not implemented");
}
