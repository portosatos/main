import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import type { Goal } from "@/api/goals";
import type { Day, WeekSummary } from "@/api/summary";
import { renderRoutes } from "@/test/render";
import { server } from "@/test/server";

import Goals from "./Goals";

// The goals page (SPEC §6.4, F8): the form of the goals (ranges of ADR-043) and the progress of
// the current ISO week, «цель выполнена N из 7 дней».

// Mon 2026-10-05 .. Sun 2026-10-11 (ISO week 2026-W41); today is Sunday.
const W41 = Array.from({ length: 7 }, (_, i) => `2026-10-${String(5 + i).padStart(2, "0")}`);

function day(date: string, steps: boolean | null, sleep: boolean | null): Day {
  const progress = (achieved: boolean | null, target: number) => ({
    target,
    percent: achieved === null ? null : achieved ? 100 : 50,
    achieved: achieved === true,
  });
  return {
    date,
    status: steps === null ? "no_data" : "complete",
    wear_minutes: steps === null ? 0 : 1380,
    steps: steps === null ? null : steps ? 9000 : 4000,
    active_minutes: null,
    sleep_minutes: sleep === null ? null : sleep ? 500 : 240,
    sleep_start: null,
    sleep_end: null,
    night_valid: sleep !== null,
    resting_hr: null,
    peak_hr: null,
    goals: { steps: progress(steps, 8000), sleep: progress(sleep, 8) },
  };
}

const METRICS_EMPTY = {
  steps: { value: null, days: 0, of: 7 },
  active_minutes: { value: null, days: 0, of: 7 },
  sleep_minutes: { value: null, days: 0, of: 7 },
  resting_hr: { value: null, days: 0, of: 7 },
  peak_hr: { value: null, days: 0, of: 7 },
};

const WEEK: WeekSummary = {
  week: "2026-W41",
  start: W41[0],
  end: W41[6],
  metrics: METRICS_EMPTY,
  goals: { steps: { achieved_days: 5, of: 7 }, sleep: { achieved_days: 3, of: 7 } },
  days: [
    day(W41[0], true, true),
    day(W41[1], true, false),
    day(W41[2], true, true),
    day(W41[3], false, false),
    day(W41[4], true, true),
    day(W41[5], true, false),
    day(W41[6], null, null),
  ],
  previous: {
    week: "2026-W40",
    start: "2026-09-28",
    end: "2026-10-04",
    metrics: METRICS_EMPTY,
    goals: { steps: { achieved_days: 0, of: 7 }, sleep: { achieved_days: 0, of: 7 } },
  },
  delta: {
    steps: null,
    active_minutes: null,
    sleep_minutes: null,
    resting_hr: null,
    peak_hr: null,
  },
};

const DEFAULT_GOALS: Goal[] = [
  { kind: "steps", target: 8000, valid_from: null },
  { kind: "sleep", target: 8, valid_from: null },
];

test("validates and saves goals", async () => {
  let goals = DEFAULT_GOALS;
  const puts: { body: unknown; csrf: string | null }[] = [];
  server.use(
    http.get("/api/auth/me", () =>
      HttpResponse.json({ id: "u", email: "demo@example.com", notify_email: null, today: "2026-10-11" }),
    ),
    http.get("/api/goals", () => HttpResponse.json(goals)),
    http.put("/api/goals", async ({ request }) => {
      const body = (await request.json()) as { steps: number; sleep: number };
      puts.push({ body, csrf: request.headers.get("X-Requested-With") });
      goals = [
        { kind: "steps", target: body.steps, valid_from: "2026-10-11T08:00:00Z" },
        { kind: "sleep", target: body.sleep, valid_from: "2026-10-11T08:00:00Z" },
      ];
      return HttpResponse.json(goals);
    }),
    http.get("/api/summary/week", ({ request }) =>
      new URL(request.url).searchParams.get("week") === "2026-W41"
        ? HttpResponse.json(WEEK)
        : HttpResponse.json({ detail: "unexpected week" }, { status: 500 }),
    ),
  );
  const user = userEvent.setup();
  renderRoutes([{ path: "/goals", element: <Goals /> }], ["/goals"]);

  // The form starts from the targets in effect now.
  const steps = await screen.findByRole("textbox", { name: "Шагов в день" });
  const sleep = screen.getByRole("textbox", { name: "Часов сна" });
  await waitFor(() => expect(steps).toHaveValue("8000"));
  expect(sleep).toHaveValue("8");

  // The week of today by the server's Clock: N of 7 days, each day by its own target.
  const week = await screen.findByRole("region", { name: /Неделя 2026-W41/ });
  expect(within(week).getByText("Шаги: цель выполнена 5 из 7 дней")).toBeInTheDocument();
  expect(within(week).getByText("Сон: цель выполнена 3 из 7 дней")).toBeInTheDocument();

  // Out of the API's ranges (ADR-043): messages under the fields, nothing is sent.
  await user.clear(steps);
  await user.type(steps, "50");
  await user.clear(sleep);
  await user.type(sleep, "17");
  await user.click(screen.getByRole("button", { name: "Сохранить" }));
  expect(await screen.findByText("Шагов — целое число от 100 до 100 000")).toBeInTheDocument();
  expect(screen.getByText("Сна — от 1 до 16 часов")).toBeInTheDocument();
  expect(steps).toHaveAttribute("aria-invalid", "true");
  expect(puts).toHaveLength(0);

  // A decimal comma is fine for hours.
  await user.clear(steps);
  await user.type(steps, "12000");
  await user.clear(sleep);
  await user.type(sleep, "7,5");
  await user.click(screen.getByRole("button", { name: "Сохранить" }));

  expect(await screen.findByText("Цели сохранены")).toBeInTheDocument();
  expect(puts).toEqual([{ body: { steps: 12000, sleep: 7.5 }, csrf: "ht" }]);
  expect(screen.queryByText("Шагов — целое число от 100 до 100 000")).not.toBeInTheDocument();
});
