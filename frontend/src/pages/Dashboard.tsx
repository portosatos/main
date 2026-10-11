import { ChevronLeft, ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";

import { useMe } from "@/api/auth";
import {
  METRICS,
  useDaySummary,
  useRangeSummary,
  useWeekSummary,
  type Day,
  type DaySummary,
  type WeekSummary,
} from "@/api/summary";
import DaysChart from "@/components/DaysChart";
import type { ChartDay } from "@/components/GapBar";
import SummaryCard from "@/components/SummaryCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  addDays,
  formatDay,
  isIsoDate,
  isIsoWeek,
  isoWeek,
  shiftWeek,
  weekMonday,
} from "@/lib/dates";
import {
  formatBase,
  formatDelta,
  formatHours,
  formatValue,
  METRIC_INFO,
  partialNote,
} from "@/lib/metrics";

// The dashboard (SPEC §6.4, F6, F7): a day or an ISO week of local dates — cards of the metrics
// with the difference to the previous period, the bases of the week's means, and bars of steps
// and sleep by day with gaps hatched. The day or week is in the URL (`?date=2026-10-07`,
// `?view=week&week=2026-W41`); without it — today by the server's Clock (`/api/auth/me`).
// Summaries are refetched on `summary.updated` by useEvents, so the page fills in while a file
// is processed.

// Days of the chart in the day view: the day and the six before it.
const CHART_DAYS = 7;

export default function Dashboard() {
  const [params] = useSearchParams();
  const view = params.get("view") === "week" ? "week" : "day";
  const dateParam = isIsoDate(params.get("date")) ? params.get("date")! : undefined;
  const weekParam = isIsoWeek(params.get("week")) ? params.get("week")! : undefined;
  const needToday = view === "day" ? !dateParam : !weekParam && !dateParam;
  const me = useMe(needToday);

  const date = dateParam ?? (needToday ? me.data?.today : undefined);
  const week = weekParam ?? (date ? isoWeek(date) : undefined);

  return (
    <div className="grid grid-cols-1 gap-6">
      <Card>
        <CardHeader className="flex flex-wrap items-center gap-3">
          <CardTitle className="mr-auto">
            <h2>Дашборд</h2>
          </CardTitle>
          <nav aria-label="Период" className="flex gap-1">
            <ViewLink active={view === "day"} to={date ? `?date=${date}` : week ? `?date=${weekMonday(week)}` : "?"}>
              День
            </ViewLink>
            <ViewLink
              active={view === "week"}
              to={week ? `?view=week&week=${week}${date ? `&date=${date}` : ""}` : "?view=week"}
            >
              Неделя
            </ViewLink>
          </nav>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-5">
          {needToday && me.isPending && <Muted>Загрузка…</Muted>}
          {needToday && me.isError && <Failure>Не удалось узнать текущую дату.</Failure>}
          {view === "day" && date && <DayView date={date} />}
          {view === "week" && week && <WeekView week={week} />}
        </CardContent>
      </Card>
    </div>
  );
}

function ViewLink({ active, to, children }: { active: boolean; to: string; children: ReactNode }) {
  return (
    <Button asChild variant={active ? "default" : "outline"} size="sm">
      <Link to={to} aria-current={active ? "page" : undefined}>
        {children}
      </Link>
    </Button>
  );
}

function Muted({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted-foreground">{children}</p>;
}

function Failure({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="text-sm text-destructive">
      {children}
    </p>
  );
}

// ‹ label › — the previous and the next period, plus a control of its own (the date picker).
function Stepper({
  label,
  previous,
  next,
  previousLabel,
  nextLabel,
  children,
}: {
  label: string;
  previous: string;
  next: string;
  previousLabel: string;
  nextLabel: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button asChild variant="outline" size="icon" aria-label={previousLabel}>
        <Link to={previous}>
          <ChevronLeft aria-hidden />
        </Link>
      </Button>
      <span className="font-medium">{label}</span>
      <Button asChild variant="outline" size="icon" aria-label={nextLabel}>
        <Link to={next}>
          <ChevronRight aria-hidden />
        </Link>
      </Button>
      {children}
      <Button asChild variant="ghost" size="sm">
        <Link to="/">Сегодня</Link>
      </Button>
    </div>
  );
}

function stepsChart(days: Day[]): ChartDay[] {
  return days.map((day) => ({ date: day.date, status: day.status, value: day.steps }));
}

function sleepChart(days: Day[]): ChartDay[] {
  return days.map((day) => ({ date: day.date, status: day.status, value: day.sleep_minutes }));
}

function Charts({ days }: { days: Day[] }) {
  const steps = new Intl.NumberFormat("ru-RU", { notation: "compact" });
  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
      <DaysChart
        title="Шаги по дням"
        days={stepsChart(days)}
        step={1000}
        color="var(--chart-2)"
        format={(v) => steps.format(v)}
      />
      <DaysChart
        title="Сон по дням"
        days={sleepChart(days)}
        step={60}
        color="var(--chart-3)"
        format={formatHours}
      />
      <p className="text-xs text-muted-foreground md:col-span-2">
        Штриховка — нет данных за день, светлый столбец «неполн.» — неполные данные (носили меньше
        12&nbsp;ч).
      </p>
    </div>
  );
}

function DayView({ date }: { date: string }) {
  const navigate = useNavigate();
  const summary = useDaySummary(date);
  const range = useRangeSummary(addDays(date, 1 - CHART_DAYS), date);

  return (
    <>
      <Stepper
        label={formatDay(date)}
        previous={`?date=${addDays(date, -1)}`}
        next={`?date=${addDays(date, 1)}`}
        previousLabel="Предыдущий день"
        nextLabel="Следующий день"
      >
        <Input
          type="date"
          aria-label="Дата"
          className="w-auto"
          value={date}
          onChange={(event) => {
            if (isIsoDate(event.target.value)) navigate(`?date=${event.target.value}`);
          }}
        />
      </Stepper>
      {summary.isPending && <Muted>Загрузка…</Muted>}
      {summary.isError && <Failure>Не удалось загрузить сводку.</Failure>}
      {summary.data && <DayCards summary={summary.data} />}
      {range.data && <Charts days={range.data} />}
    </>
  );
}

function DayCards({ summary }: { summary: DaySummary }) {
  const { day, delta } = summary;
  return (
    <>
      {day.status === "no_data" && (
        <Muted>
          За этот день данных нет. Загрузить файл можно на странице{" "}
          <Link to="/upload" className="underline">
            «Загрузка»
          </Link>
          .
        </Muted>
      )}
      {day.status === "partial" && (
        <p className="text-sm text-amber-700">{partialNote(day.wear_minutes)}</p>
      )}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {METRICS.map((metric) => (
          <SummaryCard
            key={metric}
            title={METRIC_INFO[metric].title}
            value={formatValue(metric, day[metric])}
            delta={formatDelta(metric, delta[metric])}
            note={
              metric === "sleep_minutes" && day.sleep_minutes !== null && !day.night_valid
                ? "ночь записана не полностью"
                : undefined
            }
          />
        ))}
      </div>
    </>
  );
}

function WeekView({ week }: { week: string }) {
  const summary = useWeekSummary(week);
  const monday = weekMonday(week);
  const label = `${week} · ${formatDay(monday)} — ${formatDay(addDays(monday, 6))}`;

  return (
    <>
      <Stepper
        label={label}
        previous={`?view=week&week=${shiftWeek(week, -1)}`}
        next={`?view=week&week=${shiftWeek(week, 1)}`}
        previousLabel="Предыдущая неделя"
        nextLabel="Следующая неделя"
      />
      {summary.isPending && <Muted>Загрузка…</Muted>}
      {summary.isError && <Failure>Не удалось загрузить сводку.</Failure>}
      {summary.data && <WeekCards summary={summary.data} />}
      {summary.data && <Charts days={summary.data.days} />}
    </>
  );
}

function WeekCards({ summary }: { summary: WeekSummary }) {
  const partial = summary.days.filter((day) => day.status === "partial").length;
  const empty = summary.days.filter((day) => day.status === "no_data").length;
  return (
    <>
      {(partial > 0 || empty > 0) && (
        <Muted>
          Дней без данных: {empty}, с неполными данными: {partial}. Средние шагов и активности
          считаются только по полным дням, сна — по полностью записанным ночам.
        </Muted>
      )}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {METRICS.map((metric) => {
          const { value, days, of } = summary.metrics[metric];
          return (
            <SummaryCard
              key={metric}
              title={METRIC_INFO[metric].title}
              value={formatValue(metric, value)}
              delta={formatDelta(metric, summary.delta[metric])}
              base={formatBase(metric, days, of)}
            />
          );
        })}
      </div>
    </>
  );
}
