import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "./client";

// /api/auth/* (SPEC F1, §6.3).
export type User = {
  id: string;
  email: string;
  notify_email: string | null;
};

export type Credentials = { email: string; password: string };

export const meQueryKey = ["auth", "me"] as const;

export function useMe() {
  return useQuery({
    queryKey: meQueryKey,
    queryFn: () => api.get<User>("/api/auth/me"),
    // 401 is an answer, not a failure worth retrying.
    retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
    staleTime: 5 * 60 * 1000,
  });
}

// The browser's zone becomes the first record of the user's zone history (SPEC F1, ADR-017).
export function browserTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Credentials) => api.post<User>("/api/auth/login", body),
    onSuccess: (user) => queryClient.setQueryData(meQueryKey, user),
  });
}

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Credentials) =>
      api.post<User>("/api/auth/register", { ...body, timezone: browserTimeZone() }),
    onSuccess: (user) => queryClient.setQueryData(meQueryKey, user),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>("/api/auth/logout"),
    // Nothing cached for this user may outlive the session.
    onSettled: () => queryClient.clear(),
  });
}

// A message for the form: the server's own text (it is in Russian) or a generic one.
export function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return typeof error.detail === "string" ? error.detail : fallback;
  }
  return "Сервер недоступен. Попробуйте ещё раз";
}
