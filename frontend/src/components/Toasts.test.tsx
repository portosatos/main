import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import { toast } from "sonner";

import { meQueryKey, type User } from "@/api/auth";
import type { GoalAchievedEvent } from "@/api/notifications";
import { useEvents } from "@/hooks/useEvents";
import { FakeEventSource, installFakeEventSource } from "@/test/fakeEventSource";

import Toasts from "./Toasts";

// A goal met (SPEC F8, ADR-043): every open tab gets `goal.achieved`; a toast shows only when the
// server says so (`show_toast` — today or yesterday by its Clock), so a history import does not
// flood the screen. The bell still gets the notification either way.

const ME: User = { id: "u", email: "demo@example.com", notify_email: null, today: "2026-10-11" };

function TabWithToasts() {
  useEvents();
  return <Toasts />;
}

function setup() {
  installFakeEventSource();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(meQueryKey, ME);
  render(
    <QueryClientProvider client={queryClient}>
      <TabWithToasts />
    </QueryClientProvider>,
  );
  FakeEventSource.last.emit("ready");
  return FakeEventSource.last;
}

function achieved(overrides: Partial<GoalAchievedEvent>): GoalAchievedEvent {
  return {
    kind: "steps",
    local_date: "2026-10-11",
    target: 8000,
    value: 10151,
    show_toast: true,
    notification_id: "7a1c2e0b-0000-4000-8000-000000000001",
    ...overrides,
  };
}

afterEach(() => {
  act(() => {
    toast.dismiss();
  });
  vi.unstubAllGlobals();
});

test.fails("goal.achieved with toast=true shows toast", async () => {
  const source = setup();
  source.emit("goal.achieved", achieved({}));

  expect(await screen.findByText("Цель по шагам на сегодня выполнена")).toBeInTheDocument();
  expect(screen.getByText("10 151 из 8 000 шагов")).toBeInTheDocument();

  // Yesterday's sleep: the day is named.
  source.emit(
    "goal.achieved",
    achieved({ kind: "sleep", local_date: "2026-10-10", target: 7.5, value: 8.1 }),
  );
  expect(await screen.findByText("Цель по сну на вчера выполнена")).toBeInTheDocument();
  expect(screen.getByText("8,1 из 7,5 ч")).toBeInTheDocument();
});

test.fails("goal.achieved with toast=false shows no toast", async () => {
  const source = setup();
  // A date of a history import: in the bell only.
  source.emit("goal.achieved", achieved({ local_date: "2026-09-01", show_toast: false }));
  // An event after it does show, so the first one had its chance to.
  source.emit("goal.achieved", achieved({ kind: "sleep", target: 8, value: 8.4 }));

  expect(await screen.findByText("Цель по сну на сегодня выполнена")).toBeInTheDocument();
  expect(screen.queryByText(/Цель по шагам/)).not.toBeInTheDocument();
  expect(screen.queryByText(/01\.09|2026-09-01/)).not.toBeInTheDocument();
});
