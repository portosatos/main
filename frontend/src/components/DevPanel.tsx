import { useEffect, useState, type FormEvent } from "react";

import { errorMessage } from "@/api/auth";
import { useDevClock, useSetDevOffset } from "@/api/devClock";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const HOUR = 3600;
const DAY = 24 * HOUR;

// Mailpit is published on the same host (compose: MAILPIT_UI_PORT, 8025 by default).
const mailpitUrl =
  import.meta.env.VITE_MAILPIT_URL ||
  `${window.location.protocol}//${window.location.hostname}:8025`;

const dateTime = new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "medium" });
const hoursFormat = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 });

function formatHours(seconds: number): string {
  return hoursFormat.format(seconds / HOUR);
}

// Browser time, updated every second.
function useTicker(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return now;
}

// Dev panel (SPEC F0, §6.4): the time of Clock, its offset and a link to Mailpit. Only on a dev
// stack: without /api/dev/clock (404) nothing is rendered.
export default function DevPanel() {
  const clock = useDevClock();
  const setOffset = useSetDevOffset();
  const tick = useTicker();
  // null: the field shows the current offset; a string: what the user is typing.
  const [hours, setHours] = useState<string | null>(null);
  const [inputError, setInputError] = useState<string | null>(null);

  if (!clock.data) return null;
  const state = clock.data;
  const shownNow = Date.parse(state.now) + Math.max(0, tick - state.receivedAt);

  function apply(offsetSeconds: number) {
    setInputError(null);
    setOffset.mutate(offsetSeconds, { onSuccess: () => setHours(null) });
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const value = Number((hours ?? formatHours(state.offset_seconds)).replace(",", "."));
    if (!Number.isFinite(value)) {
      setInputError("Введите число часов, например 24 или -1,5");
      return;
    }
    apply(Math.round(value * HOUR));
  }

  const error =
    inputError ?? (setOffset.isError ? errorMessage(setOffset.error, "Сдвиг не принят") : null);

  return (
    <section aria-label="Dev-панель" className="mx-auto mb-4 w-full max-w-5xl px-4 text-sm">
      <div className="grid gap-3 rounded-lg border border-dashed border-amber-400 bg-amber-50 p-3 text-amber-950">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <h2 className="font-semibold">Dev-панель</h2>
          <p>
            Время Clock:{" "}
            <time dateTime={new Date(shownNow).toISOString()}>{dateTime.format(shownNow)}</time>
          </p>
          <p>Сдвиг: {formatHours(state.offset_seconds)} ч</p>
          <a
            className="underline underline-offset-4"
            href={mailpitUrl}
            target="_blank"
            rel="noreferrer"
          >
            Mailpit (письма)
          </a>
        </div>
        <form className="flex flex-wrap items-end gap-2" onSubmit={onSubmit}>
          <div className="grid gap-1">
            <Label htmlFor="dev-offset-hours">Сдвиг, ч</Label>
            <Input
              id="dev-offset-hours"
              inputMode="decimal"
              className="w-28 bg-white"
              value={hours ?? formatHours(state.offset_seconds)}
              onChange={(event) => setHours(event.target.value)}
            />
          </div>
          <Button type="submit" size="sm" disabled={setOffset.isPending}>
            Установить
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={setOffset.isPending}
            onClick={() => apply(state.offset_seconds + HOUR)}
          >
            +1 ч
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={setOffset.isPending}
            onClick={() => apply(state.offset_seconds + DAY)}
          >
            +1 д
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={setOffset.isPending}
            onClick={() => apply(0)}
          >
            Сброс
          </Button>
        </form>
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
      </div>
    </section>
  );
}
