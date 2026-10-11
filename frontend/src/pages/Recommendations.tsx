import { Tabs } from "radix-ui";
import { useState } from "react";

import { errorMessage } from "@/api/auth";
import {
  useFeedback,
  useRecommendations,
  type Feedback,
  type Recommendation,
} from "@/api/recommendations";
import { useRules } from "@/api/rules";
import Disclaimer from "@/components/Disclaimer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { RecommendationTab } from "@/lib/queryKeys";
import { describeContext, formatDate, formatTime, STATUS_LABELS } from "@/lib/rules";

// The "Рекомендации" page (SPEC §6.4, F9): tabs «Активные» (open) and «История» (closed
// automatically or because the rule was turned off), a filter by rule, the dates of opening and
// closing and the feedback. Pressing the pressed feedback button again clears it (ADR-048).

const EMPTY: Record<RecommendationTab, string> = {
  open: "Активных рекомендаций нет.",
  history: "История пуста.",
};

const FEEDBACK_BUTTONS: { value: Feedback; label: string }[] = [
  { value: "useful", label: "Полезно" },
  { value: "not_useful", label: "Не полезно" },
];

function RecommendationCard({ rec }: { rec: Recommendation }) {
  const feedback = useFeedback();
  const headingId = `rec-${rec.id}`;
  const values = describeContext(rec.rule_code, rec.context);

  return (
    <article aria-labelledby={headingId} className="grid gap-2 rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 id={headingId} className="font-semibold">
          {rec.rule_code} {rec.title}
        </h3>
        <span
          className={`rounded-full px-2 text-xs ${rec.status === "open" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}
        >
          {STATUS_LABELS[rec.status]}
        </span>
        <span className="text-xs text-muted-foreground">за {formatDate(rec.anchor_date)}</span>
      </div>
      {values && <p className="text-sm">{values}</p>}
      <p className="text-xs text-muted-foreground">
        Открыта {formatTime(rec.opened_at)}
        {rec.resolved_at && <> · Закрыта {formatTime(rec.resolved_at)}</>}
      </p>
      <div className="flex flex-wrap gap-2">
        {FEEDBACK_BUTTONS.map(({ value, label }) => {
          const pressed = rec.feedback === value;
          return (
            <Button
              key={value}
              variant={pressed ? "default" : "outline"}
              size="sm"
              aria-pressed={pressed}
              disabled={feedback.isPending}
              onClick={() => feedback.mutate({ id: rec.id, value: pressed ? null : value })}
            >
              {label}
            </Button>
          );
        })}
      </div>
      {feedback.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(feedback.error, "Не удалось сохранить отзыв")}
        </p>
      )}
    </article>
  );
}

function RecommendationList({ tab, rule }: { tab: RecommendationTab; rule: string | null }) {
  const recommendations = useRecommendations(tab, rule);

  if (recommendations.isPending) return <p className="text-sm text-muted-foreground">Загрузка…</p>;
  if (recommendations.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        Не удалось загрузить рекомендации.
      </p>
    );
  }
  if (recommendations.data.length === 0) {
    return <p className="text-sm text-muted-foreground">{EMPTY[tab]}</p>;
  }
  return (
    <div className="grid gap-3">
      {recommendations.data.map((rec) => (
        <RecommendationCard key={rec.id} rec={rec} />
      ))}
    </div>
  );
}

const triggerClass =
  "rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent data-[state=active]:bg-accent data-[state=active]:font-medium data-[state=active]:text-foreground";

export default function Recommendations() {
  const rules = useRules();
  const [tab, setTab] = useState<RecommendationTab>("open");
  const [rule, setRule] = useState<string | null>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Рекомендации</h2>
        </CardTitle>
        <CardDescription>
          Рекомендации открываются по правилам и закрываются сами, когда ситуация меняется.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <Disclaimer />
        <Tabs.Root value={tab} onValueChange={(value) => setTab(value as RecommendationTab)}>
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <Tabs.List aria-label="Рекомендации" className="flex gap-1">
              <Tabs.Trigger value="open" className={triggerClass}>
                Активные
              </Tabs.Trigger>
              <Tabs.Trigger value="history" className={triggerClass}>
                История
              </Tabs.Trigger>
            </Tabs.List>
            <label className="ml-auto flex items-center gap-2 text-sm">
              Правило
              <select
                value={rule ?? ""}
                onChange={(event) => setRule(event.target.value || null)}
                className="h-8 rounded-md border bg-background px-2 text-sm"
              >
                <option value="">Все правила</option>
                {rules.data?.map((r) => (
                  <option key={r.code} value={r.code}>
                    {r.code} {r.title}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <Tabs.Content value="open">
            <RecommendationList tab="open" rule={rule} />
          </Tabs.Content>
          <Tabs.Content value="history">
            <RecommendationList tab="history" rule={rule} />
          </Tabs.Content>
        </Tabs.Root>
      </CardContent>
    </Card>
  );
}
