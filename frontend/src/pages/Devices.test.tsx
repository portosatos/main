import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import type { Device } from "@/api/devices";
import { renderRoutes } from "@/test/render";
import { server } from "@/test/server";

import Devices from "./Devices";

// The devices page (SPEC F2, §6.4): list, kind, last data, rename.

const WATCH: Device = {
  id: "5d1f4c1e-0000-4000-8000-000000000001",
  external_id: "watch-1",
  kind: "watch",
  name: "Часы",
  created_at: "2026-10-01T00:00:00Z",
  last_data_at: "2026-10-07T21:59:00Z",
};

const PHONE: Device = {
  id: "5d1f4c1e-0000-4000-8000-000000000002",
  external_id: "phone-1",
  kind: "phone",
  name: "Телефон",
  created_at: "2026-10-01T00:01:00Z",
  last_data_at: null,
};

test("lists devices and renames one", async () => {
  let devices = [WATCH, PHONE];
  let patch: { id: string; body: unknown; csrf: string | null } | undefined;
  server.use(
    http.get("/api/devices", () => HttpResponse.json(devices)),
    http.patch("/api/devices/:id", async ({ request, params }) => {
      const body = (await request.json()) as { name: string };
      patch = { id: String(params.id), body, csrf: request.headers.get("X-Requested-With") };
      devices = devices.map((d) => (d.id === params.id ? { ...d, name: body.name } : d));
      return HttpResponse.json(devices.find((d) => d.id === params.id));
    }),
  );
  const user = userEvent.setup();
  renderRoutes([{ path: "/devices", element: <Devices /> }], ["/devices"]);

  const table = await screen.findByRole("table", { name: "Устройства" });
  const watchRow = within(table).getByRole("row", { name: /watch-1/ });
  expect(watchRow).toHaveTextContent("Часы");
  expect(watchRow).toHaveTextContent("часы");
  const phoneRow = within(table).getByRole("row", { name: /phone-1/ });
  expect(phoneRow).toHaveTextContent("телефон");
  // A device that never sent data.
  expect(phoneRow).toHaveTextContent("нет данных");

  await user.click(within(watchRow).getByRole("button", { name: "Переименовать" }));
  const input = within(watchRow).getByRole("textbox", { name: "Имя устройства" });
  await user.clear(input);
  await user.type(input, "Мои часы");
  await user.click(within(watchRow).getByRole("button", { name: "Сохранить" }));

  await waitFor(() =>
    expect(within(table).getByRole("row", { name: /watch-1/ })).toHaveTextContent("Мои часы"),
  );
  expect(patch).toEqual({ id: WATCH.id, body: { name: "Мои часы" }, csrf: "ht" });
});

// Beyond the plan's list (step 10.1, a note of step 6.1): the time of the last data is in the
// user's zone from the history, not in the browser's (the tests run in UTC).
test("shows last data in the user's time zone", async () => {
  server.use(
    http.get("/api/auth/me", () =>
      HttpResponse.json({
        id: "u",
        email: "demo@example.com",
        notify_email: null,
        today: "2026-10-08",
        timezone: "Europe/Moscow",
      }),
    ),
    http.get("/api/devices", () => HttpResponse.json([WATCH, PHONE])),
  );
  renderRoutes([{ path: "/devices", element: <Devices /> }], ["/devices"]);

  const table = await screen.findByRole("table", { name: "Устройства" });
  // 21:59Z on Oct 7 is 00:59 on Oct 8 in Moscow.
  await waitFor(() =>
    expect(within(table).getByRole("row", { name: /watch-1/ })).toHaveTextContent(
      "08.10.2026, 00:59",
    ),
  );
});
