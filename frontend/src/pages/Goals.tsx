import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link } from "react-router";

import { errorMessage, useMe } from "@/api/auth";
import { useGoals, useSaveGoals, type Goal } from "@/api/goals";
import { useWeekSummary, type GoalKind, type WeekSummary } from "@/api/summary";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { addDays, formatDay, formatTick, isoWeek } from "@/lib/dates";
import { goalsSchema, type GoalsFields, type GoalsValues } from "@/lib/goalSchema";
import { formatWeekGoal } from "@/lib/metrics";

// The "Цели" page (SPEC §6.4, F8): the form of the goals and the progress of the current ISO week
// (today by the server's Clock). A changed goal is a new version from today on; past days keep
// the target they had (ADR-043).

const DECIMAL = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2, useGrouping: false });

const KIND_TITLES: Record<GoalKind, string> = { steps: "Шаги", sleep: "Сон" };

function fields(goals: Goal[]): GoalsFields {
  const target = (kind: GoalKind) => goals.find((goal) => goal.kind === kind)?.target ?? 0;
  return { steps: String(target("steps")), sleep: DECIMAL.format(target("sleep")) };
}

export default function Goals() {
  const goals = useGoals();
  const me = useMe();
  const week = me.data ? isoWeek(me.data.today) : undefined;

  return (
    <div className="grid grid-cols-1 gap-6">
      <Card>
        <CardHeader>
          <CardTitle>
            <h2>Цели</h2>
          </CardTitle>
          <CardDescription>
            Новая цель действует с сегодняшнего дня, прошлые дни считаются по прежней.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {goals.isPending && <p className="text-sm text-muted-foreground">Загрузка…</p>}
          {goals.isError && (
            <p role="alert" className="text-sm text-destructive">
              Не удалось загрузить цели.
            </p>
          )}
          {goals.data && <GoalsForm goals={goals.data} />}
        </CardContent>
      </Card>
      {week && <WeekProgress week={week} />}
    </div>
  );
}

function GoalsForm({ goals }: { goals: Goal[] }) {
  const save = useSaveGoals();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<GoalsFields, unknown, GoalsValues>({
    resolver: zodResolver(goalsSchema),
    // Goals changed in another tab come in here; what the user is typing stays.
    values: fields(goals),
    resetOptions: { keepDirtyValues: true },
  });

  return (
    <form
      className="grid max-w-sm gap-4"
      noValidate
      onSubmit={handleSubmit((values) => save.mutate(values))}
    >
      <div className="grid gap-2">
        <Label htmlFor="goal-steps">Шагов в день</Label>
        <Input
          id="goal-steps"
          inputMode="numeric"
          autoComplete="off"
          aria-invalid={errors.steps ? true : undefined}
          aria-describedby={errors.steps ? "goal-steps-error" : undefined}
          {...register("steps", { onChange: () => save.reset() })}
        />
        {errors.steps && (
          <p id="goal-steps-error" className="text-sm text-destructive">
            {errors.steps.message}
          </p>
        )}
      </div>
      <div className="grid gap-2">
        <Label htmlFor="goal-sleep">Часов сна</Label>
        <Input
          id="goal-sleep"
          inputMode="decimal"
          autoComplete="off"
          aria-invalid={errors.sleep ? true : undefined}
          aria-describedby={errors.sleep ? "goal-sleep-error" : undefined}
          {...register("sleep", { onChange: () => save.reset() })}
        />
        {errors.sleep && (
          <p id="goal-sleep-error" className="text-sm text-destructive">
            {errors.sleep.message}
          </p>
        )}
      </div>
      {save.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(save.error, "Не удалось сохранить цели")}
        </p>
      )}
      {save.isSuccess && (
        <p role="status" className="text-sm text-emerald-700">
          Цели сохранены
        </p>
      )}
      <Button type="submit" className="justify-self-start" disabled={save.isPending}>
        Сохранить
      </Button>
    </form>
  );
}

function WeekProgress({ week }: { week: string }) {
  const summary = useWeekSummary(week);
  const title = summary.data
    ? `Неделя ${week} · ${formatDay(summary.data.start)} — ${formatDay(addDays(summary.data.start, 6))}`
    : `Неделя ${week}`;

  return (
    <Card>
      <section aria-label={title} className="contents">
        <CardHeader>
          <CardTitle>
            <h3>{title}</h3>
          </CardTitle>
          <CardDescription>
            Каждый день — по цели, которая действовала в тот день. Подробнее — на{" "}
            <Link to={`/?view=week&week=${week}`} className="underline">
              дашборде
            </Link>
            .
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          {summary.isPending && <p className="text-sm text-muted-foreground">Загрузка…</p>}
          {summary.isError && (
            <p role="alert" className="text-sm text-destructive">
              Не удалось загрузить прогресс недели.
            </p>
          )}
          {summary.data &&
            (["steps", "sleep"] as const).map((kind) => (
              <WeekGoalRow key={kind} kind={kind} summary={summary.data} />
            ))}
        </CardContent>
      </section>
    </Card>
  );
}

// «Шаги: цель выполнена 5 из 7 дней» and a mark for each day: met, its percent or no data.
function WeekGoalRow({ kind, summary }: { kind: GoalKind; summary: WeekSummary }) {
  const { achieved_days, of } = summary.goals[kind];
  return (
    <div className="grid gap-2">
      <p className="text-sm font-medium">{`${KIND_TITLES[kind]}: ${formatWeekGoal(achieved_days, of)}`}</p>
      <ol aria-label={KIND_TITLES[kind]} className="grid grid-cols-7 gap-1 text-center text-xs">
        {summary.days.map((day) => {
          const { percent, achieved } = day.goals[kind];
          const mark = achieved ? "✓" : percent === null ? "—" : `${percent}%`;
          const state = achieved ? "выполнена" : percent === null ? "нет данных" : `${percent} %`;
          return (
            <li
              key={day.date}
              title={`${formatDay(day.date)}: ${state}`}
              className={`rounded-md border px-1 py-1.5 ${
                achieved
                  ? "border-emerald-600 bg-emerald-50 text-emerald-800"
                  : "text-muted-foreground"
              }`}
            >
              <div>{formatTick(day.date)}</div>
              <div className="font-medium">{mark}</div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
