import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "./client";

// /api/dev/clock (SPEC F0): exists only with APP_ENV=dev, otherwise 404.
export type DevClock = {
  offset_seconds: number;
  system_now: string;
  now: string;
};

// receivedAt (browser ms) lets the panel advance the shown time between requests.
export type DevClockState = DevClock & { receivedAt: number };

export const devClockKey = ["dev", "clock"] as const;

function received(clock: DevClock): DevClockState {
  return { ...clock, receivedAt: Date.now() };
}

// null: not a dev stack, the panel is not shown.
export function useDevClock() {
  return useQuery({
    queryKey: devClockKey,
    queryFn: async () => {
      try {
        return received(await api.get<DevClock>("/api/dev/clock"));
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },
    // Another tab or a script may move the clock too.
    refetchInterval: 60 * 1000,
  });
}

export function useSetDevOffset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (offsetSeconds: number) =>
      api.post<DevClock>("/api/dev/clock", { offset_seconds: offsetSeconds }),
    onSuccess: (clock) => {
      queryClient.setQueryData(devClockKey, received(clock));
      // Everything else depends on "now" (sessions, later goals and digests).
      void queryClient.invalidateQueries({ predicate: (query) => query.queryKey[0] !== "dev" });
    },
  });
}
