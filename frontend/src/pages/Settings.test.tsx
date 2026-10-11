import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import type { DigestList } from "@/api/digests";
import type { TimezoneHistory, UserSettings } from "@/api/settings";
import { renderRoutes } from "@/test/render";
import { server } from "@/test/server";

import Settings from "./Settings";

// The settings page (SPEC §6.4, F10, F11): the address for digests (a warning without it), quiet
// hours, the time zone with «действует с», the history of zones and the next planned digest.

const NO_EMAIL_WARNING = "Почта не указана: письма с рекомендациями не отправляются.";

const SETTINGS: UserSettings = {
  notify_email: null,
  quiet_enabled: false,
  quiet_start: "22:00",
  quiet_end: "08:00",
  timezone: "Europe/Moscow",
};

const MOSCOW_ONLY: TimezoneHistory = {
  current: "Europe/Moscow",
  items: [
    { tz: "Europe/Moscow", valid_from: "2026-10-01T00:00:00Z", valid_to: null, current: true },
  ],
};

function me(timezone: string) {
  return http.get("/api/auth/me", () =>
    HttpResponse.json({
      id: "u",
      email: "demo@example.com",
      notify_email: null,
      today: "2026-10-11",
      timezone,
    }),
  );
}

function renderSettings() {
  return renderRoutes([{ path: "/settings", element: <Settings /> }], ["/settings"]);
}

test("saves settings", async () => {
  let current = SETTINGS;
  const patches: { body: unknown; csrf: string | null }[] = [];
  server.use(
    me("Europe/Moscow"),
    http.get("/api/settings", () => HttpResponse.json(current)),
    http.patch("/api/settings", async ({ request }) => {
      const body = (await request.json()) as Partial<UserSettings>;
      patches.push({ body, csrf: request.headers.get("X-Requested-With") });
      current = { ...current, ...body };
      return HttpResponse.json(current);
    }),
    http.get("/api/settings/timezones", () => HttpResponse.json(MOSCOW_ONLY)),
  );
  const user = userEvent.setup();
  renderSettings();

  // No address: no digests, and the page says so (SPEC F10).
  expect(await screen.findByText(NO_EMAIL_WARNING)).toBeInTheDocument();
  const email = screen.getByRole("textbox", { name: "Почта для писем" });
  const quiet = screen.getByRole("checkbox", { name: "Тихие часы" });
  const start = screen.getByLabelText("Начало");
  const end = screen.getByLabelText("Конец");
  expect(email).toHaveValue("");
  expect(quiet).not.toBeChecked();
  expect(start).toHaveValue("22:00");
  expect(end).toHaveValue("08:00");

  // A wrong address is caught before sending.
  await user.type(email, "not-an-email");
  await user.click(screen.getByRole("button", { name: "Сохранить" }));
  expect(
    await screen.findByText("Введите адрес почты, например name@example.com"),
  ).toBeInTheDocument();
  expect(email).toHaveAttribute("aria-invalid", "true");
  expect(patches).toHaveLength(0);

  await user.clear(email);
  await user.type(email, "me@mail.example.com");
  await user.click(quiet);
  await user.clear(start);
  await user.type(start, "23:30");
  await user.clear(end);
  await user.type(end, "07:15");
  await user.click(screen.getByRole("button", { name: "Сохранить" }));

  expect(await screen.findByText("Настройки сохранены")).toBeInTheDocument();
  expect(patches).toEqual([
    {
      body: {
        notify_email: "me@mail.example.com",
        quiet_enabled: true,
        quiet_start: "23:30",
        quiet_end: "07:15",
      },
      csrf: "ht",
    },
  ]);
  await waitFor(() => expect(screen.queryByText(NO_EMAIL_WARNING)).not.toBeInTheDocument());

  // Clearing the address turns digests off: null, and the warning is back.
  await user.clear(email);
  await user.click(screen.getByRole("button", { name: "Сохранить" }));
  expect(await screen.findByText(NO_EMAIL_WARNING)).toBeInTheDocument();
  expect(patches.at(-1)?.body).toMatchObject({ notify_email: null });
});

test("shows timezone history and next digest", async () => {
  let history: TimezoneHistory = {
    current: "America/New_York",
    items: [
      {
        tz: "America/New_York",
        valid_from: "2026-10-05T12:00:00Z",
        valid_to: null,
        current: true,
      },
      {
        tz: "Europe/Moscow",
        valid_from: "2026-10-01T00:00:00Z",
        valid_to: "2026-10-05T12:00:00Z",
        current: false,
      },
    ],
  };
  const digests: DigestList = {
    notify_email: "me@mail.example.com",
    warning: null,
    pending: 2,
    items: [
      {
        id: "d2",
        status: "planned",
        local_date: "2026-10-11",
        planned_at: "2026-10-11T12:00:00Z",
        plan_reason: "quiet_hours",
        sent_at: null,
        to_email: null,
        subject: null,
        recommendations: 2,
        error: null,
      },
      {
        id: "d1",
        status: "sent",
        local_date: "2026-10-10",
        planned_at: "2026-10-10T16:15:00Z",
        plan_reason: "window",
        sent_at: "2026-10-10T16:15:20Z",
        to_email: "me@mail.example.com",
        subject: "Трекер здоровья: 1 новая рекомендация",
        recommendations: 1,
        error: null,
      },
    ],
  };
  const posts: { body: unknown; csrf: string | null }[] = [];
  server.use(
    me("America/New_York"),
    http.get("/api/settings", () =>
      HttpResponse.json({
        ...SETTINGS,
        notify_email: "me@mail.example.com",
        quiet_enabled: true,
        timezone: "America/New_York",
      }),
    ),
    http.get("/api/settings/timezones", () => HttpResponse.json(history)),
    http.post("/api/settings/timezones", async ({ request }) => {
      const body = (await request.json()) as { tz: string; valid_from?: string };
      posts.push({ body, csrf: request.headers.get("X-Requested-With") });
      history = {
        current: "Asia/Tokyo",
        items: [
          { tz: "Asia/Tokyo", valid_from: "2026-10-08T00:30:00Z", valid_to: null, current: true },
          { ...history.items[0], valid_to: "2026-10-08T00:30:00Z", current: false },
          history.items[1],
        ],
      };
      return HttpResponse.json(history, { status: 201 });
    }),
    http.get("/api/digests", () => HttpResponse.json(digests)),
  );
  const user = userEvent.setup();
  renderSettings();

  // The history, newest first; each move in the local time of its own zone.
  const list = await screen.findByRole("list", { name: "История поясов" });
  const items = within(list).getAllByRole("listitem");
  expect(items).toHaveLength(2);
  expect(items[0]).toHaveTextContent("America/New_York");
  expect(items[0]).toHaveTextContent("с 5 октября 2026, 08:00");
  expect(items[0]).toHaveTextContent("сейчас");
  expect(items[1]).toHaveTextContent("Europe/Moscow");
  expect(items[1]).toHaveTextContent("с 1 октября 2026, 03:00 по 5 октября 2026, 15:00");
  expect(items[1]).not.toHaveTextContent("сейчас");

  // The next digest in the user's zone (12:00Z is 08:00 in New York), its reason and size.
  const next = screen.getByRole("region", { name: "Ближайшее письмо" });
  await waitFor(() => expect(next).toHaveTextContent("11 октября, 08:00"));
  expect(next).toHaveTextContent("тихие часы");
  expect(next).toHaveTextContent("рекомендаций: 2");
  expect(next).toHaveTextContent("me@mail.example.com");
  expect(screen.queryByText(NO_EMAIL_WARNING)).not.toBeInTheDocument();

  // A move in the past: «действует с» goes as the local time of the new zone.
  await user.selectOptions(screen.getByRole("combobox", { name: "Новый пояс" }), "Asia/Tokyo");
  fireEvent.change(screen.getByLabelText("Действует с"), { target: { value: "2026-10-08T09:30" } });
  await user.click(screen.getByRole("button", { name: "Сменить пояс" }));

  await waitFor(() => expect(within(list).getAllByRole("listitem")).toHaveLength(3));
  expect(posts).toEqual([
    { body: { tz: "Asia/Tokyo", valid_from: "2026-10-08T09:30" }, csrf: "ht" },
  ]);
  expect(within(list).getAllByRole("listitem")[0]).toHaveTextContent("Asia/Tokyo");
});
