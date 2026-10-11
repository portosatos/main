import { z } from "zod";

// The settings form (SPEC F10, F11): an empty address means no digests; quiet hours are local
// times "HH:MM", as the API takes them (ADR-051).
const EMAIL_MESSAGE = "Введите адрес почты, например name@example.com";
const TIME_MESSAGE = "Время — в формате ЧЧ:ММ";
const hhmm = z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/, TIME_MESSAGE);

export const settingsSchema = z.object({
  notify_email: z
    .string()
    .trim()
    .refine((value) => value === "" || z.email().safeParse(value).success, EMAIL_MESSAGE)
    .transform((value) => (value === "" ? null : value)),
  quiet_enabled: z.boolean(),
  quiet_start: hhmm,
  quiet_end: hhmm,
});

export type SettingsFields = z.input<typeof settingsSchema>;
export type SettingsValues = z.output<typeof settingsSchema>;
