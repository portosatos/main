// ISO week of a local date: "2026-10-07" → "2026-W41" (the format of /api/summary/week).
export function isoWeek(date: string): string {
  const day = new Date(`${date}T00:00:00Z`);
  // The week belongs to the year of its Thursday.
  day.setUTCDate(day.getUTCDate() + 4 - (day.getUTCDay() || 7));
  const year = day.getUTCFullYear();
  const week = Math.ceil(((day.getTime() - Date.UTC(year, 0, 1)) / 86_400_000 + 1) / 7);
  return `${year}-W${String(week).padStart(2, "0")}`;
}
