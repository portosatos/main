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

test.fails("hidden when /api/dev/clock returns 404", async () => {
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

test.fails("sets offset and shows new time", async () => {
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
