import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Day, DaySummary, Deltas, WeekSummary } from "@/api/summary";
import { useEvents } from "@/hooks/useEvents";
import { FakeEventSource, installFakeEventSource } from "@/test/fakeEventSource";
import { renderRoutes } from "@/test/render";
import { server } from "@/test/server";

import Dashboard from "./Dashboard";

// The dashboard (SPEC §6.4, F6, F7): cards of a day or an ISO week with the difference to the
// previous period and the bases of the week's means. The date or week comes in the URL.

const NO_DELTA: Deltas = {
  steps: null,
  active_minutes: null,
  sleep_minutes: null,
  resting_hr: null,
  peak_hr: null,
};

const CARDS = ["Сон", "Шаги", "Активные минуты", "Пульс в покое", "Пиковый пульс"];

function noData(date: string): Day {
  return {
    date,
    status: "no_data",
    wear_minutes: 0,
    steps: null,
    active_minutes: null,
    sleep_minutes: null,
    sleep_start: null,
    sleep_end: null,
    night_valid: false,
    resting_hr: null,
    peak_hr: null,
  };
}

function complete(date: string, overrides: Partial<Day> = {}): Day {
  return {
    date,
    status: "complete",
    wear_minutes: 1380,
    steps: 8000,
    active_minutes: 40,
    sleep_minutes: 450,
    sleep_start: `${date}T19:30:00Z`,
    sleep_end: `${date}T03:00:00Z`,
    night_valid: true,
    resting_hr: 58,
    peak_hr: 150,
    ...overrides,
  };
}

// Mon 2026-10-05 .. Sun 2026-10-11 (ISO week 2026-W41).
const W41 = Array.from({ length: 7 }, (_, i) => `2026-10-${String(5 + i).padStart(2, "0")}`);

// GET /api/summary/day for one date and /api/summary/range (the chart) with no data.
function serveDay(summary: DaySummary) {
  server.use(
    http.get("/api/summary/day", ({ request }) => {
      const date = new URL(request.url).searchParams.get("date");
      return date === summary.day.date
        ? HttpResponse.json(summary)
        : HttpResponse.json({ detail: "unexpected date" }, { status: 500 });
    }),
    http.get("/api/summary/range", ({ request }) => {
      const params = new URL(request.url).searchParams;
      const days: Day[] = [];
      for (
        let d = new Date(`${params.get("from")}T00:00:00Z`);
        d <= new Date(`${params.get("to")}T00:00:00Z`);
        d.setUTCDate(d.getUTCDate() + 1)
      ) {
        days.push(noData(d.toISOString().slice(0, 10)));
      }
      return HttpResponse.json(days);
    }),
  );
}

function DashboardWithEvents() {
  useEvents();
  return <Dashboard />;
}

function renderDashboard(url: string) {
  return renderRoutes([{ path: "/", element: <DashboardWithEvents /> }], [url]);
}

async function card(name: string) {
  return screen.findByRole("region", { name });
}

beforeEach(() => {
  installFakeEventSource();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test.fails("no_data day shows «нет данных», not 0", async () => {
  serveDay({ day: noData("2026-10-07"), previous: noData("2026-10-06"), delta: NO_DELTA });
  renderDashboard("/?date=2026-10-07");

  for (const name of CARDS) {
    const region = await card(name);
    expect(within(region).getByText("нет данных")).toBeInTheDocument();
    // No zero instead of the missing value (SPEC F6).
    expect(within(region).queryAllByText(/(^|\s)0(\s|$)/)).toHaveLength(0);
  }
});

test.fails("partial day shows «неполные данные (носили N ч)»", async () => {
  serveDay({
    day: complete("2026-10-07", { status: "partial", wear_minutes: 300, steps: 1500 }),
    previous: noData("2026-10-06"),
    delta: NO_DELTA,
  });
  renderDashboard("/?date=2026-10-07");

  expect(await screen.findByText("неполные данные (носили 5 ч)")).toBeInTheDocument();
  // The values of a partial day are shown, with the mark.
  expect(within(await card("Шаги")).getByText("1 500")).toBeInTheDocument();
});

test.fails("missing comparison shows «нет данных для сравнения»", async () => {
  serveDay({
    day: complete("2026-10-07", { steps: 8000 }),
    previous: complete("2026-10-06", { steps: 6000, night_valid: false }),
    // Steps compare, sleep does not (the previous night is not valid, ADR-037).
    delta: { ...NO_DELTA, steps: { abs: 2000, pct: 33.3 } },
  });
  renderDashboard("/?date=2026-10-07");

  expect(within(await card("Шаги")).getByText("+2 000 (+33,3 %)")).toBeInTheDocument();
  for (const name of CARDS.filter((name) => name !== "Шаги")) {
    expect(within(await card(name)).getByText("нет данных для сравнения")).toBeInTheDocument();
  }
});

test.fails("week cards show base counts («сон: 6 из 7 ночей»)", async () => {
  const week: WeekSummary = {
    week: "2026-W41",
    start: W41[0],
    end: W41[6],
    metrics: {
      steps: { value: 9000, days: 5, of: 7 },
      active_minutes: { value: 50, days: 5, of: 7 },
      sleep_minutes: { value: 450, days: 6, of: 7 },
      resting_hr: { value: null, days: 0, of: 7 },
      peak_hr: { value: 165, days: 4, of: 7 },
    },
    days: W41.map((date) => complete(date)),
    previous: {
      week: "2026-W40",
      start: "2026-09-28",
      end: "2026-10-04",
      metrics: {
        steps: { value: 6000, days: 7, of: 7 },
        active_minutes: { value: 50, days: 7, of: 7 },
        sleep_minutes: { value: 420, days: 7, of: 7 },
        resting_hr: { value: 60, days: 7, of: 7 },
        peak_hr: { value: 170, days: 7, of: 7 },
      },
    },
    delta: { ...NO_DELTA, steps: { abs: 3000, pct: 50 }, sleep_minutes: { abs: 30, pct: 7.1 } },
  };
  server.use(
    http.get("/api/summary/week", ({ request }) =>
      new URL(request.url).searchParams.get("week") === "2026-W41"
        ? HttpResponse.json(week)
        : HttpResponse.json({ detail: "unexpected week" }, { status: 500 }),
    ),
  );
  renderDashboard("/?view=week&week=2026-W41");

  expect(within(await card("Сон")).getByText("сон: 6 из 7 ночей")).toBeInTheDocument();
  expect(within(await card("Шаги")).getByText("шаги: 5 из 7 дней")).toBeInTheDocument();
  expect(within(await card("Шаги")).getByText("9 000")).toBeInTheDocument();
  expect(within(await card("Шаги")).getByText("+3 000 (+50 %)")).toBeInTheDocument();
  expect(
    within(await card("Активные минуты")).getByText("активные минуты: 5 из 7 дней"),
  ).toBeInTheDocument();
  expect(within(await card("Пиковый пульс")).getByText("пиковый пульс: 4 из 7 дней")).toBeInTheDocument();
  // An empty base: «нет данных», not 0.
  const resting = await card("Пульс в покое");
  expect(within(resting).getByText("нет данных")).toBeInTheDocument();
  expect(within(resting).getByText("пульс в покое: 0 из 7 дней")).toBeInTheDocument();
});

test.fails("refetches on summary.updated", async () => {
  let steps = 1000;
  server.use(
    http.get("/api/summary/day", () =>
      HttpResponse.json({
        day: complete("2026-10-07", { steps }),
        previous: noData("2026-10-06"),
        delta: NO_DELTA,
      }),
    ),
    http.get("/api/summary/range", () => HttpResponse.json([])),
  );
  renderDashboard("/?date=2026-10-07");
  expect(await within(await card("Шаги")).findByText("1 000")).toBeInTheDocument();

  // The worker counted more of the day: the event names the date, the card asks again.
  steps = 5000;
  FakeEventSource.last.emit("ready");
  FakeEventSource.last.emit("summary.updated", { dates: ["2026-10-07"] });
  await waitFor(() => expect(within(screen.getByRole("region", { name: "Шаги" })).getByText("5 000")).toBeInTheDocument());
});
