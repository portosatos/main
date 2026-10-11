import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { goalsKey, summaryKeys } from "@/lib/queryKeys";

import { api } from "./client";
import type { GoalKind } from "./summary";

// /api/goals (SPEC F8, §6.3, ADR-043): the targets in effect now; PUT makes a new version.
// Other tabs learn of a change from `goal.changed` (useEvents).

export type Goal = {
  kind: GoalKind;
  // Steps a day, or hours of sleep.
  target: number;
  // When the target was set; null for the default (8000 steps, 8 h).
  valid_from: string | null;
};

export type GoalsInput = { steps: number; sleep: number };

export function useGoals() {
  return useQuery({ queryKey: goalsKey, queryFn: () => api.get<Goal[]>("/api/goals") });
}

export function useSaveGoals() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: GoalsInput) => api.put<Goal[]>("/api/goals", body),
    onSuccess: (goals) => {
      queryClient.setQueryData(goalsKey, goals);
      // Today's progress is counted by the new target.
      void queryClient.invalidateQueries({ queryKey: summaryKeys.all });
    },
  });
}
