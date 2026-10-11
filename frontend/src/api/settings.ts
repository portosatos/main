import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { meQueryKey } from "@/api/auth";
import { digestsKey, settingsKey, timezonesKey } from "@/lib/queryKeys";

import { api } from "./client";

// /api/settings and /api/settings/timezones (SPEC F10, F11, §6.3, ADR-051): the address for
// digests, quiet hours and the time zone history. Other tabs learn of a change from
// `settings.changed` (useEvents); the dates a move changed come with `summary.updated`.

export type UserSettings = {
  // null: no digests are sent (SPEC F10).
  notify_email: string | null;
  quiet_enabled: boolean;
  // Local times "HH:MM".
  quiet_start: string;
  quiet_end: string;
  // The zone in effect now.
  timezone: string;
};

export type SettingsInput = Partial<Omit<UserSettings, "timezone">>;

export type TimezoneRecord = {
  tz: string;
  // null: in effect since always — the zone kept by a move earlier than the history.
  valid_from: string | null;
  // The next record's valid_from; null for the last one.
  valid_to: string | null;
  current: boolean;
};

// Newest first.
export type TimezoneHistory = { current: string; items: TimezoneRecord[] };

// valid_from without an offset is the local time of the new zone; without it — now.
export type TimezoneInput = { tz: string; valid_from?: string };

export function useSettings() {
  return useQuery({
    queryKey: settingsKey,
    queryFn: () => api.get<UserSettings>("/api/settings"),
  });
}

export function useSaveSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SettingsInput) => api.patch<UserSettings>("/api/settings", body),
    onSuccess: (settings) => {
      queryClient.setQueryData(settingsKey, settings);
      // The address in /api/auth/me and the plan of the next digest.
      void queryClient.invalidateQueries({ queryKey: meQueryKey });
      void queryClient.invalidateQueries({ queryKey: digestsKey });
    },
  });
}

export function useTimezones() {
  return useQuery({
    queryKey: timezonesKey,
    queryFn: () => api.get<TimezoneHistory>("/api/settings/timezones"),
  });
}

export function useAddTimezone() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: TimezoneInput) => api.post<TimezoneHistory>("/api/settings/timezones", body),
    onSuccess: (history) => {
      queryClient.setQueryData(timezonesKey, history);
      // Today and the zone of /api/auth/me, the zone of the form, the next digest.
      void queryClient.invalidateQueries({ queryKey: meQueryKey });
      void queryClient.invalidateQueries({
        queryKey: settingsKey,
        exact: true,
      });
      void queryClient.invalidateQueries({ queryKey: digestsKey });
    },
  });
}

// IANA zones the browser knows; UTC is not among them in every engine.
export function timeZones(): string[] {
  const zones = Intl.supportedValuesOf("timeZone");
  return zones.includes("UTC") ? zones : [...zones, "UTC"].sort();
}
