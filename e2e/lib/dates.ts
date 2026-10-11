import { TIMEZONE } from "./env";

// Local dates of the scenarios as YYYY-MM-DD strings, counted from `today` of /api/auth/me.
export function addDays(date: string, days: number): string {
  const day = new Date(`${date}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() + days);
  return day.toISOString().slice(0, 10);
}

const LOCAL = new Intl.DateTimeFormat("en-CA", {
  timeZone: TIMEZONE,
  hourCycle: "h23",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

// The wall clock of a moment in the users' zone, as numbers.
export function localParts(moment: string | Date) {
  const parts = Object.fromEntries(LOCAL.formatToParts(new Date(moment)).map((part) => [part.type, part.value]));
  const [year, month, day, hour, minute, second] = ["year", "month", "day", "hour", "minute", "second"].map(
    (type) => Number(parts[type]),
  );
  return { year, month, day, hour, minute, second };
}

// The local date (YYYY-MM-DD) and time (HH:MM) of a moment in the users' zone (TIMEZONE).
export function localDate(moment: string | Date): string {
  const { year, month, day } = localParts(moment);
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function localTime(moment: string | Date): string {
  const { hour, minute } = localParts(moment);
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

// The moment (ms since the epoch) when the users' zone shows `date` (YYYY-MM-DD) at `hhmm`.
export function localMoment(date: string, hhmm: string): number {
  const [hour, minute] = hhmm.split(":").map(Number);
  const wall = Date.parse(`${date}T00:00:00Z`) + (hour * 60 + minute) * 60_000;
  // The zone's offset at a guess, then once more at the result (a DST change between them).
  let moment = wall;
  for (let i = 0; i < 2; i++) {
    const p = localParts(new Date(moment));
    const shown = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
    moment = wall - (shown - moment);
  }
  return moment;
}
