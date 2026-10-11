// Query keys shared by the pages and by useEvents, which invalidates them on server events
// (SPEC F12). Summary keys come with the dashboard (step 6.1) in this shape.
export const ingestJobsKey = ["ingest", "jobs"] as const;
export const devicesKey = ["devices"] as const;
export const goalsKey = ["goals"] as const;
export const notificationsKey = ["notifications"] as const;
export const rulesKey = ["rules"] as const;
export const digestsKey = ["digests"] as const;

// The tabs of the recommendations page: open ones, and the closed ones.
export type RecommendationTab = "open" | "history";

export const recommendationKeys = {
  all: ["recommendations"] as const,
  list: (tab: RecommendationTab, rule: string | null) =>
    ["recommendations", tab, rule ?? "all"] as const,
};

export const summaryKeys = {
  all: ["summary"] as const,
  day: (date: string) => ["summary", "day", date] as const,
  week: (week: string) => ["summary", "week", week] as const,
  range: (from: string, to: string) => ["summary", "range", from, to] as const,
};
