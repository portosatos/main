// /api/recommendations (SPEC F9, §6.3): the active ones and the history. Hooks come with step 8.3.

export type RecommendationStatus = "open" | "resolved" | "closed_rule_disabled";
export type Feedback = "useful" | "not_useful";

export type Recommendation = {
  id: string;
  rule_code: string;
  title: string;
  status: RecommendationStatus;
  opened_at: string;
  // The local date the rule fired on.
  anchor_date: string;
  // The values the rule fired on.
  context: Record<string, unknown>;
  resolved_at: string | null;
  // "auto" or "rule_disabled".
  resolve_reason: string | null;
  feedback: Feedback | null;
  feedback_at: string | null;
};
