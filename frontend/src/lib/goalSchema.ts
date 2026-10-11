import { z } from "zod";

// The goals form (SPEC F8): the same ranges as the API (ADR-043). Fields are text, so hours take
// a decimal comma as well as a point ("7,5").
const STEPS_MESSAGE = "Шагов — целое число от 100 до 100 000";
const SLEEP_MESSAGE = "Сна — от 1 до 16 часов";

export const goalsSchema = z.object({
  steps: z
    .string()
    .trim()
    .regex(/^\d+$/, STEPS_MESSAGE)
    .transform(Number)
    .pipe(z.number().int().min(100, STEPS_MESSAGE).max(100_000, STEPS_MESSAGE)),
  sleep: z
    .string()
    .trim()
    .regex(/^\d+([.,]\d+)?$/, SLEEP_MESSAGE)
    .transform((value) => Number(value.replace(",", ".")))
    .pipe(z.number().min(1, SLEEP_MESSAGE).max(16, SLEEP_MESSAGE)),
});

export type GoalsFields = z.input<typeof goalsSchema>;
export type GoalsValues = z.output<typeof goalsSchema>;
