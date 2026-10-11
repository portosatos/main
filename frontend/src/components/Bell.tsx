import { Bell as BellIcon } from "lucide-react";
import { Popover } from "radix-ui";

import {
  useMarkAllRead,
  useNotifications,
  type GoalAchievedPayload,
  type Notification,
} from "@/api/notifications";
import { Button } from "@/components/ui/button";
import { formatGoalMet, GOAL_TITLES } from "@/lib/metrics";

// The bell in the header (SPEC §6.4, F8): the unread count of GET /api/notifications and the
// newest notifications. useEvents asks for them again on `notification.created` and
// `notifications.read`, so every open tab shows the same count. Opening the list does not mark
// it read: «Прочитать все» does.

// "2026-10-11" → "11.10.2026": a local date as it is.
function formatDate(date: string): string {
  const [year, month, day] = date.split("-");
  return `${day}.${month}.${year}`;
}

function describe(notification: Notification): { text: string; date?: string } {
  if (notification.type === "goal.achieved") {
    const { kind, local_date, target, value } = notification.payload as GoalAchievedPayload;
    return {
      text: `${GOAL_TITLES[kind]} выполнена: ${formatGoalMet(kind, value, target)}`,
      date: formatDate(local_date),
    };
  }
  return { text: notification.type };
}

export default function Bell() {
  const notifications = useNotifications();
  const markAllRead = useMarkAllRead();
  const unread = notifications.data?.unread;
  const items = notifications.data?.items ?? [];

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative"
          aria-label={unread === undefined ? "Уведомления" : `Уведомления, непрочитанных: ${unread}`}
        >
          <BellIcon aria-hidden />
          {unread !== undefined && unread > 0 && (
            <span
              aria-hidden
              className="absolute -top-0.5 -right-0.5 min-w-4 rounded-full bg-destructive px-1 text-[10px] leading-4 font-semibold text-white"
            >
              {unread > 99 ? "99+" : unread}
            </span>
          )}
        </Button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={6}
          collisionPadding={16}
          className="z-50 w-[min(22rem,calc(100vw-2rem))] rounded-xl border bg-popover p-3 text-popover-foreground shadow-md"
        >
          <div className="mb-2 flex items-center gap-2">
            <h2 className="mr-auto text-sm font-semibold">Уведомления</h2>
            <Button
              variant="ghost"
              size="sm"
              disabled={!unread || markAllRead.isPending}
              onClick={() => markAllRead.mutate()}
            >
              Прочитать все
            </Button>
          </div>
          {notifications.isError && (
            <p role="alert" className="text-sm text-destructive">
              Не удалось загрузить уведомления.
            </p>
          )}
          {notifications.data && items.length === 0 && (
            <p className="text-sm text-muted-foreground">Уведомлений пока нет.</p>
          )}
          {items.length > 0 && (
            <ul aria-label="Уведомления" className="grid max-h-80 gap-1 overflow-y-auto">
              {items.map((notification) => {
                const { text, date } = describe(notification);
                const isUnread = notification.read_at === null;
                return (
                  <li
                    key={notification.id}
                    className={`rounded-md px-2 py-1.5 text-sm ${isUnread ? "bg-accent font-medium" : ""}`}
                  >
                    <div>{text}</div>
                    {date && <div className="text-xs text-muted-foreground">за {date}</div>}
                  </li>
                );
              })}
            </ul>
          )}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
