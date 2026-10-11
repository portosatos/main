// /api/settings and /api/settings/timezones (SPEC F10, F11, §6.3): the address for digests, quiet
// hours and the time zone history. Comes with step 10.1.

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
  valid_from: string;
  // The next record's valid_from; null for the last one.
  valid_to: string | null;
  current: boolean;
};

// Newest first.
export type TimezoneHistory = { current: string; items: TimezoneRecord[] };

// valid_from without an offset is the local time of the new zone; without it — now.
export type TimezoneInput = { tz: string; valid_from?: string };
