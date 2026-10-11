import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { recommendationKeys, rulesKey } from "@/lib/queryKeys";

import { api } from "./client";

// /api/rules (SPEC F9, §6.3, ADR-048): R1–R6 with the user's switch. Turning a rule off closes
// its open recommendation, turning it on evaluates it at once; other tabs hear `rule.toggled`.

export type Rule = {
  code: string;
  title: string;
  description: string;
  // The thresholds of the rule (rules.params); the user does not edit them.
  params: Record<string, number>;
  enabled: boolean;
  // When the user last switched the rule; null if never.
  changed_at: string | null;
};

export function useRules() {
  return useQuery({ queryKey: rulesKey, queryFn: () => api.get<Rule[]>("/api/rules") });
}

export function useSwitchRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ code, enabled }: { code: string; enabled: boolean }) =>
      api.patch<Rule>(`/api/rules/${code}`, { enabled }),
    onSuccess: (rule) => {
      queryClient.setQueryData<Rule[]>(rulesKey, (old) =>
        old?.map((r) => (r.code === rule.code ? rule : r)),
      );
      // A recommendation may have been closed or opened.
      void queryClient.invalidateQueries({ queryKey: recommendationKeys.all });
    },
  });
}
