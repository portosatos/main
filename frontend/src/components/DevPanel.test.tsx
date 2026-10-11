import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { renderRoutes } from "@/test/render";
import { server } from "@/test/server";

import DevPanel from "./DevPanel";

// Tests run with TZ=UTC (vitest.config.ts), so the shown local time is predictable.
const SYSTEM_NOW = "2026-10-10T15:00:00Z";

function renderPanel() {
  return renderRoutes([{ path: "/", element: <DevPanel /> }]);
}

test("hidden when /api/dev/clock returns 404", async () => {
  let requested = false;
  server.use(
    http.get("/api/dev/clock", () => {
      requested = true;
      return HttpResponse.json({ detail: "Not Found" }, { status: 404 });
    }),
  );

  renderPanel();

  await waitFor(() => expect(requested).toBe(true));
  // Let the answer reach the component before checking that nothing is shown.
  await new Promise((resolve) => setTimeout(resolve, 50));
  expect(screen.queryByRole("region", { name: "Dev-панель" })).not.toBeInTheDocument();
});

// The digest queue (plan step 9.2): the planned digest and the sent ones, from /api/digests.
test("shows digest queue", async () => {
  server.use(
    http.get("/api/dev/clock", () =>
      HttpResponse.json({ offset_seconds: 0, system_now: SYSTEM_NOW, now: SYSTEM_NOW }),
    ),
    http.get("/api/digests", () =>
      HttpResponse.json({
        notify_email: "demo@example.com",
        warning: null,
        pending: 1,
        items: [
          {
            id: "d2",
            status: "planned",
            local_date: "2026-10-11",
            planned_at: "2026-10-11T05:00:00Z",
            plan_reason: "quiet_hours",
            sent_at: null,
            to_email: null,
            subject: null,
            recommendations: 1,
            error: null,
          },
          {
            id: "d1",
            status: "sent",
            local_date: "2026-10-10",
            planned_at: "2026-10-10T15:15:00Z",
            plan_reason: "window",
            sent_at: "2026-10-10T15:15:20Z",
            to_email: "demo@example.com",
            subject: "Трекер здоровья: 2 новые рекомендации",
            recommendations: 2,
            error: null,
          },
        ],
      }),
    ),
  );
  renderPanel();

  const panel = await screen.findByRole("region", { name: "Dev-панель" });
  const queue = await within(panel).findByRole("table", { name: "Очередь дайджестов" });
  const [, planned, sent] = within(queue).getAllByRole("row");
  expect(planned).toHaveTextContent("запланирован");
  expect(planned).toHaveTextContent("11.10.2026, 05:00");
  expect(planned).toHaveTextContent("тихие часы");
  expect(planned).toHaveTextContent("1");
  expect(sent).toHaveTextContent("отправлен");
  expect(sent).toHaveTextContent("10.10.2026, 15:15:20");
  expect(sent).toHaveTextContent("окно");
  expect(sent).toHaveTextContent("2");
  expect(within(panel).getByText(/Ждут письма: 1/)).toBeInTheDocument();
});

test("sets offset and shows new time", async () => {
  // A stateful fake of the dev clock API: GET returns what the last POST set.
  let offset = 0;
  let posted: unknown;
  const state = () => ({
    offset_seconds: offset,
    system_now: SYSTEM_NOW,
    now: new Date(Date.parse(SYSTEM_NOW) + offset * 1000).toISOString(),
  });
  server.use(
    http.get("/api/dev/clock", () => HttpResponse.json(state())),
    http.post("/api/dev/clock", async ({ request }) => {
      posted = await request.json();
      offset = (posted as { offset_seconds: number }).offset_seconds;
      return HttpResponse.json(state());
    }),
  );
  const user = userEvent.setup();
  renderPanel();

  const panel = await screen.findByRole("region", { name: "Dev-панель" });
  expect(await within(panel).findByText(/10\.10\.2026, 15:00/)).toBeInTheDocument();

  const input = within(panel).getByLabelText("Сдвиг, ч");
  await user.clear(input);
  await user.type(input, "24");
  await user.click(within(panel).getByRole("button", { name: "Установить" }));

  expect(await within(panel).findByText(/11\.10\.2026, 15:00/)).toBeInTheDocument();
  expect(posted).toEqual({ offset_seconds: 86400 });
  expect(within(panel).getByRole("link", { name: /Mailpit/ })).toHaveAttribute(
    "href",
    expect.stringContaining(":8025"),
  );
});
