import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { recommendationKeys, type RecommendationTab } from "@/lib/queryKeys";

import { api } from "./client";

// /api/recommendations (SPEC F9, §6.3, ADR-048): the active ones and the history, newest first,
// and the feedback on any of them. Other tabs hear `recommendation.*` (useEvents).

export type RecommendationStatus = "open" | "resolved" | "closed_rule_disabled";
export type Feedback = "useful" | "not_useful";

export type Recommendation = {
  id: string;
  rule_code: string;
  title: string;
  status: RecommendationStatus;
  opened_at: string;
  // The local date the rule fired on.
  anchor_date: string;
  // The values the rule fired on.
  context: Record<string, unknown>;
  resolved_at: string | null;
  // "auto" or "rule_disabled".
  resolve_reason: string | null;
  feedback: Feedback | null;
  feedback_at: string | null;
};

// The statuses of each tab.
const TAB_STATUSES: Record<RecommendationTab, RecommendationStatus[]> = {
  open: ["open"],
  history: ["resolved", "closed_rule_disabled"],
};

export function useRecommendations(tab: RecommendationTab, rule: string | null) {
  const params = new URLSearchParams(TAB_STATUSES[tab].map((status) => ["status", status]));
  if (rule) params.append("rule", rule);
  return useQuery({
    queryKey: recommendationKeys.list(tab, rule),
    queryFn: () => api.get<Recommendation[]>(`/api/recommendations?${params}`),
  });
}

// Set (PUT) or clear (null → DELETE) the feedback.
export function useFeedback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, value }: { id: string; value: Feedback | null }) =>
      value
        ? api.put<Recommendation>(`/api/recommendations/${id}/feedback`, { value })
        : api.delete<Recommendation>(`/api/recommendations/${id}/feedback`),
    onSuccess: (saved) => {
      queryClient.setQueriesData<Recommendation[]>({ queryKey: recommendationKeys.all }, (old) =>
        old?.map((r) => (r.id === saved.id ? saved : r)),
      );
    },
  });
}
