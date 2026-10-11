import { useQuery } from "@tanstack/react-query";

import { summaryKeys } from "@/lib/queryKeys";

import { api } from "./client";

// /api/summary/* (SPEC F7, §6.3, docs/API.md): a day, an ISO week and a range of local dates.
// Their keys are summaryKeys, so useEvents refetches them on `summary.updated`.

export type DayStatus = "no_data" | "partial" | "complete";

// Goals in a summary (SPEC F8, ADR-043): a day by the target in effect on it, a week as
// «цель выполнена N из 7 дней». Sleep is counted on the wake day, in hours.
export type GoalKind = "steps" | "sleep";

// `percent` is rounded down (100 only when met) and may pass 100; null without a value.
export type GoalProgress = { target: number; percent: number | null; achieved: boolean };

export type WeekGoal = { achieved_days: number; of: number };

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
  goals: Record<GoalKind, GoalProgress>;
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
  goals: Record<GoalKind, WeekGoal>;
};

export type WeekSummary = WeekTotals & { days: Day[]; previous: WeekTotals; delta: Deltas };

export function useDaySummary(date: string | undefined) {
  return useQuery({
    queryKey: summaryKeys.day(date ?? ""),
    queryFn: () => api.get<DaySummary>(`/api/summary/day?date=${date}`),
    enabled: date !== undefined,
  });
}

export function useWeekSummary(week: string | undefined) {
  return useQuery({
    queryKey: summaryKeys.week(week ?? ""),
    queryFn: () => api.get<WeekSummary>(`/api/summary/week?week=${week}`),
    enabled: week !== undefined,
  });
}

export function useRangeSummary(from: string | undefined, to: string | undefined) {
  return useQuery({
    queryKey: summaryKeys.range(from ?? "", to ?? ""),
    queryFn: () => api.get<Day[]>(`/api/summary/range?from=${from}&to=${to}`),
    enabled: from !== undefined && to !== undefined,
  });
}
