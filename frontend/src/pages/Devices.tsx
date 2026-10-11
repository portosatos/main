import { useState } from "react";
import { Link } from "react-router";

import { errorMessage, useMe } from "@/api/auth";
import { ApiError } from "@/api/client";
import { useDevices, useRenameDevice, type Device } from "@/api/devices";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

// The "Устройства" page (SPEC F2, §6.4): the devices the uploads brought, their kind, the time of
// their last data and renaming.

const KIND_LABELS: Record<Device["kind"], string> = { watch: "часы", phone: "телефон" };

// In the user's zone from the history (/api/auth/me), not the browser's; the browser's until it
// is known.
function formatTime(iso: string, timeZone: string | undefined): string {
  return new Date(iso).toLocaleString("ru-RU", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone,
  });
}

function renameError(error: unknown): string {
  // Pydantic's 422 detail is a list: the rule is simpler to say.
  if (error instanceof ApiError && error.status === 422) return "Имя — от 1 до 100 символов";
  return errorMessage(error, "Не удалось переименовать");
}

export default function Devices() {
  const devices = useDevices();

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Устройства</h2>
        </CardTitle>
        <CardDescription>
          Устройства появляются сами при загрузке данных. Здесь можно дать им понятные имена.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {devices.isPending && <p className="text-sm text-muted-foreground">Загрузка…</p>}
        {devices.isError && (
          <p role="alert" className="text-sm text-destructive">
            Не удалось загрузить устройства.
          </p>
        )}
        {devices.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Устройств пока нет — они появятся после первой{" "}
            <Link to="/upload" className="underline">
              загрузки
            </Link>
            .
          </p>
        )}
        {devices.data && devices.data.length > 0 && (
          // `relative`: the sr-only header (absolute) is clipped by the scrolling box too.
          <div className="relative overflow-x-auto">
            <table aria-label="Устройства" className="w-full text-left text-sm">
              <thead className="text-muted-foreground">
                <tr>
                  <th className="py-2 pr-4 font-medium">Имя</th>
                  <th className="py-2 pr-4 font-medium">Тип</th>
                  <th className="py-2 pr-4 font-medium">Последние данные</th>
                  <th className="py-2 font-medium">
                    <span className="sr-only">Действия</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {devices.data.map((device) => (
                  <DeviceRow key={device.id} device={device} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function DeviceRow({ device }: { device: Device }) {
  const timeZone = useMe().data?.timezone;
  const rename = useRenameDevice();
  const [draft, setDraft] = useState<string | null>(null);

  const save = () => {
    if (draft === null) return;
    rename.mutate({ id: device.id, name: draft }, { onSuccess: () => setDraft(null) });
  };

  return (
    <tr className="border-t align-top">
      <td className="py-2 pr-4">
        {draft === null ? (
          <span className="font-medium">{device.name}</span>
        ) : (
          <form
            className="flex flex-col gap-1"
            onSubmit={(event) => {
              event.preventDefault();
              save();
            }}
          >
            <Input
              aria-label="Имя устройства"
              value={draft}
              maxLength={100}
              onChange={(event) => setDraft(event.target.value)}
              autoFocus
            />
            {rename.isError && (
              <span role="alert" className="text-xs text-destructive">
                {renameError(rename.error)}
              </span>
            )}
          </form>
        )}
        <div className="text-xs text-muted-foreground">{device.external_id}</div>
      </td>
      <td className="py-2 pr-4">{KIND_LABELS[device.kind]}</td>
      <td className="py-2 pr-4 whitespace-nowrap">
        {device.last_data_at ? formatTime(device.last_data_at, timeZone) : "нет данных"}
      </td>
      <td className="py-2">
        {draft === null ? (
          <Button variant="outline" size="sm" onClick={() => setDraft(device.name)}>
            Переименовать
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button size="sm" disabled={rename.isPending} onClick={save}>
              Сохранить
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                rename.reset();
                setDraft(null);
              }}
            >
              Отмена
            </Button>
          </div>
        )}
      </td>
    </tr>
  );
}
