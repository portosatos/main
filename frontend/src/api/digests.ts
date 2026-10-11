import { useQuery } from "@tanstack/react-query";

import { digestsKey } from "@/lib/queryKeys";

import { api } from "./client";

// /api/digests (SPEC F10, ADR-050): the planned digest and the sent ones. The worker moves the plan
// every 30 s; a sent digest comes with the digest.sent event (useEvents).

export type PlanReason = "window" | "max_delay" | "daily_limit" | "quiet_hours";

export type Digest = {
  id: string;
  status: "planned" | "sent";
  local_date: string;
  planned_at: string;
  plan_reason: PlanReason;
  sent_at: string | null;
  to_email: string | null;
  subject: string | null;
  // Pending recommendations (planned) or those in the letter (sent).
  recommendations: number;
  error: string | null;
};

export type DigestList = {
  notify_email: string | null;
  warning: "no_notify_email" | null;
  pending: number;
  items: Digest[];
};

// Why the digest goes at that time (SPEC F10: the planner's rules).
export const PLAN_REASONS: Record<PlanReason, string> = {
  window: "окно",
  max_delay: "потолок",
  daily_limit: "1 письмо в сутки",
  quiet_hours: "тихие часы",
};

export function useDigests() {
  return useQuery({
    queryKey: digestsKey,
    queryFn: () => api.get<DigestList>("/api/digests"),
    // The plan moves with the dispatcher's tick, without an event.
    refetchInterval: 30 * 1000,
  });
}
