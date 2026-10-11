import type { Delta, GoalKind, Metric } from "@/api/summary";

// How the dashboard shows the metrics of a summary (SPEC F7): titles, units, the words of the
// week's bases («сон: 6 из 7 ночей») and the difference with the previous period.

const integer = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
const tenths = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 });

export function formatMinutes(minutes: number): string {
  const total = Math.round(Math.abs(minutes));
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  if (!hours) return `${rest} мин`;
  return rest ? `${hours} ч ${rest} мин` : `${hours} ч`;
}

export function formatHours(minutes: number): string {
  return `${tenths.format(minutes / 60)} ч`;
}

type MetricInfo = {
  title: string;
  // The metric in the base label: «шаги: 5 из 7 дней».
  base: string;
  units: "дней" | "ночей";
  format: (value: number) => string;
};

const pulse = (value: number) => `${tenths.format(Math.abs(value))} уд/мин`;

export const METRIC_INFO: Record<Metric, MetricInfo> = {
  sleep_minutes: { title: "Сон", base: "сон", units: "ночей", format: formatMinutes },
  steps: { title: "Шаги", base: "шаги", units: "дней", format: (v) => integer.format(Math.abs(v)) },
  active_minutes: {
    title: "Активные минуты",
    base: "активные минуты",
    units: "дней",
    format: (v) => `${integer.format(Math.abs(v))} мин`,
  },
  resting_hr: { title: "Пульс в покое", base: "пульс в покое", units: "дней", format: pulse },
  peak_hr: { title: "Пиковый пульс", base: "пиковый пульс", units: "дней", format: pulse },
};

export function formatValue(metric: Metric, value: number | null): string | null {
  return value === null ? null : METRIC_INFO[metric].format(value);
}

function sign(value: number): string {
  return value > 0 ? "+" : "−";
}

// «+2 000 (+33,3 %)»; null — no difference to show.
export function formatDelta(metric: Metric, delta: Delta | null): string | null {
  if (delta === null) return null;
  if (delta.abs === 0) return "без изменений";
  const abs = `${sign(delta.abs)}${METRIC_INFO[metric].format(delta.abs)}`;
  if (delta.pct === null) return abs;
  return `${abs} (${sign(delta.pct)}${tenths.format(Math.abs(delta.pct))} %)`;
}

export function formatBase(metric: Metric, days: number, of: number): string {
  const info = METRIC_INFO[metric];
  return `${info.base}: ${days} из ${of} ${info.units}`;
}

// «неполные данные (носили 5 ч)» for a partial day (SPEC F6).
export function partialNote(wearMinutes: number): string {
  return `неполные данные (носили ${tenths.format(wearMinutes / 60)} ч)`;
}

// Goals (SPEC F8): steps a day and hours of sleep, as the targets and the met values are shown.
export const GOAL_TITLES: Record<GoalKind, string> = { steps: "Цель по шагам", sleep: "Цель по сну" };

// «8 000 шагов», «7,5 ч».
export function formatGoalAmount(kind: GoalKind, amount: number): string {
  return kind === "steps" ? `${integer.format(amount)} шагов` : `${tenths.format(amount)} ч`;
}

// «10 151 из 8 000 шагов», «8,1 из 7,5 ч».
export function formatGoalMet(kind: GoalKind, value: number, target: number): string {
  const shown = kind === "steps" ? integer.format(value) : tenths.format(value);
  return `${shown} из ${formatGoalAmount(kind, target)}`;
}

export function formatWeekGoal(days: number, of: number): string {
  return `цель выполнена ${days} из ${of} дней`;
}
