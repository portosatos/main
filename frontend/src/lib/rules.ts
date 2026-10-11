import type { RecommendationStatus } from "@/api/recommendations";

// How the rules and recommendations are shown (SPEC F9, docs/RULES.md): the thresholds of
// rules.params in words, the statuses and the disclaimer.

export const DISCLAIMER =
  "Рекомендации носят информационный характер и не заменяют консультацию врача. " +
  "Если вас беспокоит самочувствие, обратитесь к специалисту.";

export const STATUS_LABELS: Record<RecommendationStatus, string> = {
  open: "активна",
  resolved: "закрыта автоматически",
  closed_rule_disabled: "правило отключено",
};

const percent = new Intl.NumberFormat("ru-RU", { style: "percent", maximumFractionDigits: 0 });

type Threshold = (value: number) => string;

// Per rule, as the keys of the same name mean different things in different rules.
const THRESHOLDS: Record<string, Record<string, Threshold>> = {
  R1: {
    nights: (v) => `Ночей подряд: ${v}`,
    short_hours: (v) => `Короткая ночь: меньше ${v} ч`,
    close_hours: (v) => `Закрывается: ночь от ${v} ч`,
  },
  R2: {
    days: (v) => `Полных дней подряд: ${v}`,
    goal_share: (v) => `Мало шагов: меньше ${percent.format(v)} цели`,
  },
  R3: {
    days: (v) => `Дней подряд: ${v}`,
    baseline_days: (v) => `База: среднее за ${v} дней до них`,
    baseline_min_values: (v) => `Значений в базе: не меньше ${v}`,
    rise_bpm: (v) => `Срабатывает: база + ${v} уд/мин и выше`,
    close_bpm: (v) => `Закрывается: ниже базы + ${v} уд/мин`,
  },
  R4: {
    min_nights: (v) => `Валидных ночей в каждой неделе: не меньше ${v}`,
    drop_minutes: (v) => `Срабатывает: сон меньше на ${v} мин и больше`,
    close_minutes: (v) => `Закрывается: разница меньше ${v} мин`,
  },
  R5: {
    nights: (v) => `Ночей в окне: ${v}`,
    min_nights: (v) => `Валидных ночей: не меньше ${v}`,
    stdev_minutes: (v) => `Срабатывает: разброс отбоя больше ${v} мин`,
    close_minutes: (v) => `Закрывается: разброс меньше ${v} мин`,
  },
  R6: {
    days: (v) => `Полных дней подряд: ${v}`,
    active_minutes: (v) => `Мало активности: меньше ${v} активных минут`,
  },
};

// The thresholds of a rule in words, in the order of its params.
export function describeThresholds(code: string, params: Record<string, number>): string[] {
  return Object.entries(params).map(([key, value]) => {
    const describe = THRESHOLDS[code]?.[key];
    return describe ? describe(value) : `${key}: ${value}`;
  });
}

// "2026-10-11" → "11.10.2026": a local date as it is.
export function formatDate(date: string): string {
  const [year, month, day] = date.split("-");
  return `${day}.${month}.${year}`;
}

// A moment in the browser's zone: "11.10.2026, 15:40".
export function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}
