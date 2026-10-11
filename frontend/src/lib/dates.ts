// ISO week of a local date: "2026-10-07" → "2026-W41" (the format of /api/summary/week).
export function isoWeek(date: string): string {
  const day = new Date(`${date}T00:00:00Z`);
  // The week belongs to the year of its Thursday.
  day.setUTCDate(day.getUTCDate() + 4 - (day.getUTCDay() || 7));
  const year = day.getUTCFullYear();
  const week = Math.ceil(((day.getTime() - Date.UTC(year, 0, 1)) / 86_400_000 + 1) / 7);
  return `${year}-W${String(week).padStart(2, "0")}`;
}

const DAY_MS = 86_400_000;

function utc(date: string): Date {
  return new Date(`${date}T00:00:00Z`);
}

export function isIsoDate(value: string | null): value is string {
  return value !== null && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(utc(value).getTime());
}

export function isIsoWeek(value: string | null): value is string {
  return value !== null && /^\d{4}-W\d{2}$/.test(value);
}

export function addDays(date: string, days: number): string {
  return new Date(utc(date).getTime() + days * DAY_MS).toISOString().slice(0, 10);
}

// Monday of an ISO week: "2026-W41" → "2026-10-05". Week 1 is the week of January 4.
export function weekMonday(week: string): string {
  const [year, number] = week.split("-W").map(Number);
  const jan4 = new Date(Date.UTC(year, 0, 4));
  const firstMonday = jan4.getTime() - ((jan4.getUTCDay() || 7) - 1) * DAY_MS;
  return new Date(firstMonday + (number - 1) * 7 * DAY_MS).toISOString().slice(0, 10);
}

export function shiftWeek(week: string, weeks: number): string {
  return isoWeek(addDays(weekMonday(week), weeks * 7));
}

// "ср, 7 октября" — a local date as is, whatever the browser's zone.
export function formatDay(date: string): string {
  return utc(date).toLocaleDateString("ru-RU", {
    weekday: "short",
    day: "numeric",
    month: "long",
    timeZone: "UTC",
  });
}

// "пн 5" — a tick of a chart.
export function formatTick(date: string): string {
  const weekday = utc(date).toLocaleDateString("ru-RU", { weekday: "short", timeZone: "UTC" });
  return `${weekday} ${utc(date).getUTCDate()}`;
}
