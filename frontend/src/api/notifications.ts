// /api/notifications (SPEC F8, §6.3, ADR-043): the bell's feed, newest first, and the unread count.

export type GoalAchievedPayload = {
  kind: "steps" | "sleep";
  local_date: string;
  target: number;
  // Steps, or hours to 0.1.
  value: number;
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
