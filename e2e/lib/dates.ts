// Local dates of the scenarios as YYYY-MM-DD strings, counted from `today` of /api/auth/me.
export function addDays(date: string, days: number): string {
  const day = new Date(`${date}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() + days);
  return day.toISOString().slice(0, 10);
}

// The local date (YYYY-MM-DD) and time (HH:MM) of a moment in the users' zone (TIMEZONE).
export function localDate(_moment: string | Date): string {
  throw new Error("step 12.2: not implemented");
}

export function localTime(_moment: string | Date): string {
  throw new Error("step 12.2: not implemented");
}
