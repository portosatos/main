import { z } from "zod";

// Validation of the login and registration forms; messages are shown as is (SPEC §4: Russian UI).
const email = z.string().trim().min(1, "Введите email").pipe(z.email("Некорректный email"));

export const loginSchema = z.object({
  email,
  password: z.string().min(1, "Введите пароль"),
});

export const registerSchema = z.object({
  email,
  // The same bounds as the API (RegisterRequest).
  password: z
    .string()
    .min(1, "Введите пароль")
    .min(8, "Пароль — не меньше 8 символов")
    .max(128, "Пароль — не больше 128 символов"),
});

export type AuthValues = z.infer<typeof loginSchema>;
