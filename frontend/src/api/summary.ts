// /api/summary/* (SPEC F7, §6.3, docs/API.md): a day, an ISO week and a range of local dates.

export type DayStatus = "no_data" | "partial" | "complete";

// A date without data is no_data with nulls, never zeros (SPEC F6).
export type Day = {
  date: string;
  status: DayStatus;
  wear_minutes: number;
  steps: number | null;
  active_minutes: number | null;
  sleep_minutes: number | null;
  sleep_start: string | null;
  sleep_end: string | null;
  night_valid: boolean;
  resting_hr: number | null;
  peak_hr: number | null;
};

export const METRICS = ["sleep_minutes", "steps", "active_minutes", "resting_hr", "peak_hr"] as const;
export type Metric = (typeof METRICS)[number];

// Current minus previous; null: "нет данных для сравнения".
export type Delta = { abs: number; pct: number | null };
export type Deltas = Record<Metric, Delta | null>;

export type DaySummary = { day: Day; previous: Day; delta: Deltas };

// The metric over its base: `days` of `of` (SPEC F7); value null when the base is empty.
export type WeekMetric = { value: number | null; days: number; of: number };

export type WeekTotals = {
  week: string;
  start: string;
  end: string;
  metrics: Record<Metric, WeekMetric>;
};

export type WeekSummary = WeekTotals & { days: Day[]; previous: WeekTotals; delta: Deltas };
