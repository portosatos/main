import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState, type FormEvent } from "react";
import { useForm, useWatch } from "react-hook-form";

import { errorMessage } from "@/api/auth";
import { PLAN_REASONS, useDigests } from "@/api/digests";
import {
  timeZones,
  useAddTimezone,
  useSaveSettings,
  useSettings,
  useTimezones,
  type TimezoneRecord,
  type UserSettings,
} from "@/api/settings";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDateTime } from "@/lib/dates";
import { settingsSchema, type SettingsFields, type SettingsValues } from "@/lib/settingsSchema";

// The "Настройки" page (SPEC §6.4, F10, F11, ADR-051): the address for digests (a warning without
// it), quiet hours, the time zone with «действует с» and its history, the next planned digest.
// Times are shown in the user's zone from the history, not in the browser's.

const NO_EMAIL_WARNING = "Почта не указана: письма с рекомендациями не отправляются.";

function fields(settings: UserSettings): SettingsFields {
  return {
    notify_email: settings.notify_email ?? "",
    quiet_enabled: settings.quiet_enabled,
    quiet_start: settings.quiet_start,
    quiet_end: settings.quiet_end,
  };
}

export default function Settings() {
  const settings = useSettings();

  return (
    <div className="grid grid-cols-1 gap-6">
      <Card>
        <CardHeader>
          <CardTitle>
            <h2>Настройки</h2>
          </CardTitle>
          <CardDescription>
            Рекомендации приходят на почту одним письмом не чаще раза в сутки; в тихие часы письмо
            ждёт их окончания.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          {settings.isPending && <p className="text-sm text-muted-foreground">Загрузка…</p>}
          {settings.isError && (
            <p role="alert" className="text-sm text-destructive">
              Не удалось загрузить настройки.
            </p>
          )}
          {settings.data?.notify_email === null && (
            <p
              role="alert"
              className="rounded-md border border-amber-500 bg-amber-50 p-3 text-sm text-amber-900"
            >
              {NO_EMAIL_WARNING}
            </p>
          )}
          {settings.data && <SettingsForm settings={settings.data} />}
        </CardContent>
      </Card>
      <TimezoneCard />
      {settings.data && <NextDigest timeZone={settings.data.timezone} />}
    </div>
  );
}

function SettingsForm({ settings }: { settings: UserSettings }) {
  const save = useSaveSettings();
  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<SettingsFields, unknown, SettingsValues>({
    resolver: zodResolver(settingsSchema),
    // Settings changed in another tab come in here; what the user is typing stays.
    values: fields(settings),
    resetOptions: { keepDirtyValues: true },
  });
  const [start, end, enabled] = useWatch({
    control,
    name: ["quiet_start", "quiet_end", "quiet_enabled"],
  });

  return (
    <form
      className="grid max-w-sm gap-4"
      noValidate
      onSubmit={handleSubmit((values) => save.mutate(values))}
    >
      <div className="grid gap-2">
        <Label htmlFor="notify-email">Почта для писем</Label>
        <Input
          id="notify-email"
          type="email"
          autoComplete="email"
          aria-invalid={errors.notify_email ? true : undefined}
          aria-describedby={errors.notify_email ? "notify-email-error" : "notify-email-hint"}
          {...register("notify_email", { onChange: () => save.reset() })}
        />
        {errors.notify_email ? (
          <p id="notify-email-error" className="text-sm text-destructive">
            {errors.notify_email.message}
          </p>
        ) : (
          <p id="notify-email-hint" className="text-sm text-muted-foreground">
            Пустое поле — письма не отправляются.
          </p>
        )}
      </div>
      <fieldset className="grid gap-3">
        <div className="flex items-center gap-2">
          <input
            id="quiet-enabled"
            type="checkbox"
            className="size-4"
            {...register("quiet_enabled", { onChange: () => save.reset() })}
          />
          <Label htmlFor="quiet-enabled">Тихие часы</Label>
        </div>
        <div className="flex gap-4">
          <div className="grid gap-2">
            <Label htmlFor="quiet-start">Начало</Label>
            <Input
              id="quiet-start"
              type="time"
              aria-invalid={errors.quiet_start ? true : undefined}
              {...register("quiet_start", { onChange: () => save.reset() })}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="quiet-end">Конец</Label>
            <Input
              id="quiet-end"
              type="time"
              aria-invalid={errors.quiet_end ? true : undefined}
              {...register("quiet_end", { onChange: () => save.reset() })}
            />
          </div>
        </div>
        {(errors.quiet_start || errors.quiet_end) && (
          <p className="text-sm text-destructive">
            {(errors.quiet_start ?? errors.quiet_end)?.message}
          </p>
        )}
        <p className="text-sm text-muted-foreground">
          {enabled && start === end
            ? "Начало совпадает с концом — тихие часы выключены."
            : "По местному времени; могут переходить через полночь, например 22:00–08:00."}
        </p>
      </fieldset>
      {save.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(save.error, "Не удалось сохранить настройки")}
        </p>
      )}
      {save.isSuccess && (
        <p role="status" className="text-sm text-emerald-700">
          Настройки сохранены
        </p>
      )}
      <Button type="submit" className="justify-self-start" disabled={save.isPending}>
        Сохранить
      </Button>
    </form>
  );
}

// "с 5 октября 2026, 08:00 по …" in the zone of the record itself: the time on the clocks there.
function period(record: TimezoneRecord): string {
  const from = record.valid_from
    ? `с ${formatDateTime(record.valid_from, record.tz, true)}`
    : "с начала истории";
  const to = record.valid_to ? ` по ${formatDateTime(record.valid_to, record.tz, true)}` : "";
  return from + to;
}

function TimezoneCard() {
  const history = useTimezones();
  const add = useAddTimezone();
  const zones = useMemo(() => timeZones(), []);
  const [tz, setTz] = useState("");
  const [validFrom, setValidFrom] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!tz) return;
    add.mutate(validFrom ? { tz, valid_from: validFrom } : { tz }, {
      onSuccess: () => {
        setTz("");
        setValidFrom("");
      },
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h3>Часовой пояс</h3>
        </CardTitle>
        <CardDescription>
          Дни считаются по поясу, который действовал в момент события. После смены пояса затронутые
          дни и правила пересчитываются; итоги за период не меняются.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        {history.isPending && <p className="text-sm text-muted-foreground">Загрузка…</p>}
        {history.isError && (
          <p role="alert" className="text-sm text-destructive">
            Не удалось загрузить историю поясов.
          </p>
        )}
        {history.data && (
          <>
            <p className="text-sm">
              Сейчас: <span className="font-medium">{history.data.current}</span>
            </p>
            <ul aria-label="История поясов" className="grid gap-1 text-sm">
              {history.data.items.map((record) => (
                <li key={`${record.tz}-${record.valid_from ?? "start"}`}>
                  <span className="font-medium">{record.tz}</span> — {period(record)}
                  {record.current && <span className="text-emerald-700"> · сейчас</span>}
                </li>
              ))}
            </ul>
          </>
        )}
        <form className="grid max-w-sm gap-4" noValidate onSubmit={submit}>
          <div className="grid gap-2">
            <Label htmlFor="new-tz">Новый пояс</Label>
            <select
              id="new-tz"
              className="h-9 rounded-md border border-input bg-transparent px-3 text-sm"
              value={tz}
              onChange={(event) => {
                setTz(event.target.value);
                add.reset();
              }}
            >
              <option value="">Выберите пояс</option>
              {zones.map((zone) => (
                <option key={zone} value={zone}>
                  {zone}
                </option>
              ))}
            </select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="tz-valid-from">Действует с</Label>
            <Input
              id="tz-valid-from"
              type="datetime-local"
              aria-describedby="tz-valid-from-hint"
              value={validFrom}
              onChange={(event) => {
                setValidFrom(event.target.value);
                add.reset();
              }}
            />
            <p id="tz-valid-from-hint" className="text-sm text-muted-foreground">
              По часам нового пояса; пусто — сейчас. Время в будущем не принимается. Переезд в
              прошлом действует до следующей записи истории.
            </p>
          </div>
          {add.isError && (
            <p role="alert" className="text-sm text-destructive">
              {errorMessage(add.error, "Не удалось сменить пояс")}
            </p>
          )}
          {add.isSuccess && (
            <p role="status" className="text-sm text-emerald-700">
              Пояс сохранён, дни пересчитываются
            </p>
          )}
          <Button type="submit" className="justify-self-start" disabled={!tz || add.isPending}>
            Сменить пояс
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

// The next planned digest (ADR-050): the dispatcher's plan, moved every 30 s.
function NextDigest({ timeZone }: { timeZone: string }) {
  const digests = useDigests();
  const planned = digests.data?.items.find((digest) => digest.status === "planned");

  return (
    <Card>
      <section aria-label="Ближайшее письмо" className="contents">
        <CardHeader>
          <CardTitle>
            <h3>Ближайшее письмо</h3>
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          {digests.isPending && <p className="text-muted-foreground">Загрузка…</p>}
          {digests.data?.warning === "no_notify_email" && (
            <p className="text-muted-foreground">Писем не будет: почта не указана.</p>
          )}
          {digests.data && !digests.data.warning && !planned && (
            <p className="text-muted-foreground">Запланированных писем нет.</p>
          )}
          {planned && (
            <p>
              <time dateTime={planned.planned_at}>
                {formatDateTime(planned.planned_at, timeZone)}
              </time>{" "}
              ({PLAN_REASONS[planned.plan_reason]}), рекомендаций: {planned.recommendations}
              {digests.data?.notify_email && <> · на {digests.data.notify_email}</>}
            </p>
          )}
        </CardContent>
      </section>
    </Card>
  );
}
