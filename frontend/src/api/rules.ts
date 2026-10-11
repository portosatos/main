// /api/rules (SPEC F9, §6.3): R1–R6 with the user's switch. Hooks come with step 8.3.

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
