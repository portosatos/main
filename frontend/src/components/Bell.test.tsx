import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import type { Notification, NotificationList } from "@/api/notifications";
import { useEvents } from "@/hooks/useEvents";
import { FakeEventSource, installFakeEventSource } from "@/test/fakeEventSource";
import { server } from "@/test/server";

import Bell from "./Bell";

// The bell in the header (SPEC §6.4, F8, F12): the count is `unread` of GET /api/notifications,
// asked again on `notification.created` — in every open tab.

const ACHIEVED: Notification = {
  id: "7a1c2e0b-0000-4000-8000-000000000001",
  type: "goal.achieved",
  payload: { kind: "steps", local_date: "2026-10-11", target: 8000, value: 10151 },
  created_at: "2026-10-11T07:30:00Z",
  read_at: null,
};

function TabWithBell() {
  useEvents();
  return <Bell />;
}

function renderBell() {
  installFakeEventSource();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <TabWithBell />
    </QueryClientProvider>,
  );
  return FakeEventSource.last;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

test("unread count updates on notification.created", async () => {
  let feed: NotificationList = { items: [], unread: 0 };
  server.use(http.get("/api/notifications", () => HttpResponse.json(feed)));
  const source = renderBell();

  expect(
    await screen.findByRole("button", { name: "Уведомления, непрочитанных: 0" }),
  ).toBeInTheDocument();

  // The worker met a goal: the event comes before goal.achieved, the bell asks for the count.
  feed = { items: [ACHIEVED], unread: 1 };
  source.emit("ready");
  source.emit("notification.created", { id: ACHIEVED.id, type: ACHIEVED.type });

  const bell = await screen.findByRole("button", { name: "Уведомления, непрочитанных: 1" });
  expect(bell).toHaveTextContent("1");
});

test("lists notifications and marks all read", async () => {
  const older: Notification = {
    id: "7a1c2e0b-0000-4000-8000-000000000002",
    type: "goal.achieved",
    payload: { kind: "sleep", local_date: "2026-10-10", target: 7.5, value: 8.1 },
    created_at: "2026-10-10T03:00:00Z",
    read_at: "2026-10-10T05:00:00Z",
  };
  let feed: NotificationList = { items: [ACHIEVED, older], unread: 1 };
  const reads: { body: unknown; csrf: string | null }[] = [];
  server.use(
    http.get("/api/notifications", () => HttpResponse.json(feed)),
    http.post("/api/notifications/read", async ({ request }) => {
      reads.push({ body: await request.json(), csrf: request.headers.get("X-Requested-With") });
      feed = { items: feed.items.map((n) => ({ ...n, read_at: "2026-10-11T08:00:00Z" })), unread: 0 };
      return HttpResponse.json({ unread: 0 });
    }),
  );
  const user = userEvent.setup();
  renderBell();

  await user.click(await screen.findByRole("button", { name: "Уведомления, непрочитанных: 1" }));
  const list = await screen.findByRole("list", { name: "Уведомления" });
  const items = within(list).getAllByRole("listitem");
  expect(items).toHaveLength(2);
  expect(items[0]).toHaveTextContent("Цель по шагам выполнена: 10 151 из 8 000 шагов");
  expect(items[0]).toHaveTextContent("11.10.2026");
  expect(items[1]).toHaveTextContent("Цель по сну выполнена: 8,1 из 7,5 ч");

  await user.click(screen.getByRole("button", { name: "Прочитать все" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Уведомления, непрочитанных: 0" })).toBeInTheDocument(),
  );
  expect(reads).toEqual([{ body: {}, csrf: "ht" }]);
});
