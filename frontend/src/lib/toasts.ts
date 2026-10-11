import type { QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { meQueryKey, type User } from "@/api/auth";
import type { GoalAchievedEvent } from "@/api/notifications";
import { addDays, formatDay } from "@/lib/dates";
import { formatGoalMet } from "@/lib/metrics";

// Toasts of server events (SPEC F8, ADR-043), shown by <Toasts /> of the tab.

const KIND_WORDS = { steps: "по шагам", sleep: "по сну" } as const;

// «на сегодня», «на вчера» by the server's today; another date as it is.
function onDay(date: string, today: string | undefined): string {
  if (date === today) return "на сегодня";
  if (today && date === addDays(today, -1)) return "на вчера";
  return `на ${formatDay(date)}`;
}

// A goal met: a toast only when the server says so (today or yesterday by its Clock); a date of
// a history import goes to the bell only. The notification id keeps one toast per achievement.
export function showGoalToast(queryClient: QueryClient, event: GoalAchievedEvent): void {
  if (!event.show_toast) return;
  const today = queryClient.getQueryData<User>(meQueryKey)?.today;
  toast.success(`Цель ${KIND_WORDS[event.kind]} ${onDay(event.local_date, today)} выполнена`, {
    id: event.notification_id,
    description: formatGoalMet(event.kind, event.value, event.target),
  });
}
