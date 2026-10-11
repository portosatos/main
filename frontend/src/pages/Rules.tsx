import { Switch } from "radix-ui";

import { errorMessage } from "@/api/auth";
import { useRules, useSwitchRule, type Rule } from "@/api/rules";
import Disclaimer from "@/components/Disclaimer";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { describeThresholds } from "@/lib/rules";

// The "Правила" page (SPEC §6.4, F9): a card per rule — title, description, thresholds and the
// switch. Off closes the rule's open recommendation («правило отключено»), on evaluates it at
// once (ADR-048).

function RuleCard({ rule }: { rule: Rule }) {
  const switchRule = useSwitchRule();
  const name = `${rule.code} ${rule.title}`;
  const headingId = `rule-${rule.code}`;

  return (
    <article aria-labelledby={headingId} className="grid gap-2 rounded-xl border bg-card p-4">
      <div className="flex items-start gap-3">
        <h3 id={headingId} className="mr-auto font-semibold">
          {name}
        </h3>
        <Switch.Root
          checked={rule.enabled}
          disabled={switchRule.isPending}
          onCheckedChange={(enabled) => switchRule.mutate({ code: rule.code, enabled })}
          aria-label={`Правило ${rule.code} включено`}
          className="relative h-6 w-11 shrink-0 rounded-full bg-input transition-colors data-[state=checked]:bg-primary disabled:opacity-50"
        >
          <Switch.Thumb className="block size-5 translate-x-0.5 rounded-full bg-background shadow transition-transform data-[state=checked]:translate-x-[22px]" />
        </Switch.Root>
      </div>
      <p className="text-sm">{rule.description}</p>
      <ul aria-label="Пороги" className="list-disc pl-5 text-sm text-muted-foreground">
        {describeThresholds(rule.code, rule.params).map((text) => (
          <li key={text}>{text}</li>
        ))}
      </ul>
      {!rule.enabled && <p className="text-xs text-muted-foreground">Правило выключено и не оценивается.</p>}
      {switchRule.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(switchRule.error, "Не удалось переключить правило")}
        </p>
      )}
    </article>
  );
}

export default function Rules() {
  const rules = useRules();

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Правила</h2>
        </CardTitle>
        <CardDescription>
          По этим правилам приложение открывает рекомендации. Пороги заданы заранее; правило можно
          выключить.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <Disclaimer />
        {rules.isPending && <p className="text-sm text-muted-foreground">Загрузка…</p>}
        {rules.isError && (
          <p role="alert" className="text-sm text-destructive">
            Не удалось загрузить правила.
          </p>
        )}
        {rules.data?.map((rule) => <RuleCard key={rule.code} rule={rule} />)}
      </CardContent>
    </Card>
  );
}
