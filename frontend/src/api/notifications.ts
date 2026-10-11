import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { notificationsKey } from "@/lib/queryKeys";

import { api } from "./client";

// /api/notifications (SPEC F8, §6.3, ADR-043): the bell's feed, newest first, and the unread count.
// Other tabs learn of changes from `notification.created` and `notifications.read` (useEvents).

export type GoalAchievedPayload = {
  kind: "steps" | "sleep";
  local_date: string;
  target: number;
  // Steps, or hours to 0.1.
  value: number;
};

// A recommendation opened by a rule (ADR-048).
export type RecommendationOpenedPayload = {
  recommendation_id: string;
  rule_code: string;
  title: string;
  anchor_date: string;
};

export type Notification = {
  id: string;
  type: string;
  payload: Record<string, unknown>;
  created_at: string;
  read_at: string | null;
};

export type NotificationList = { items: Notification[]; unread: number };

// The goal.achieved event (docs/API.md): a toast only when show_toast (today or yesterday).
export type GoalAchievedEvent = GoalAchievedPayload & {
  show_toast: boolean;
  notification_id: string;
};

// The newest 50, as many as the bell shows.
export function useNotifications() {
  return useQuery({
    queryKey: notificationsKey,
    queryFn: () => api.get<NotificationList>("/api/notifications?limit=50"),
  });
}

export function useMarkAllRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ unread: number }>("/api/notifications/read", {}),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: notificationsKey }),
  });
}
