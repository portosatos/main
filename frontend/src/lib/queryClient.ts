import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/api/client";

// 4xx is an answer (401, 404, 422), not a failure worth retrying; network and 5xx get two retries.
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
        refetchOnWindowFocus: false,
      },
    },
  });
}
