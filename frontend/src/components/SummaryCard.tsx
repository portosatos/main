import { useId, type ReactNode } from "react";

// A metric of the dashboard (SPEC §6.4): the value or «нет данных» (never 0 for a missing one),
// the difference with the previous period or «нет данных для сравнения», the base of a week's
// mean, a note and the goal's progress (children).
export default function SummaryCard({
  title,
  value,
  delta,
  base,
  note,
  children,
}: {
  title: string;
  value: string | null;
  delta: string | null;
  base?: string;
  note?: string;
  children?: ReactNode;
}) {
  const id = useId();
  return (
    <section
      aria-labelledby={id}
      className="flex min-w-0 flex-col gap-1 rounded-xl border bg-card p-4 text-card-foreground"
    >
      <h3 id={id} className="text-sm text-muted-foreground">
        {title}
      </h3>
      <p className={value === null ? "text-xl text-muted-foreground" : "text-2xl font-semibold"}>
        {value ?? "нет данных"}
      </p>
      <p className={`text-sm ${delta === null ? "text-muted-foreground" : ""}`}>
        {delta ?? "нет данных для сравнения"}
      </p>
      {base && <p className="text-xs text-muted-foreground">{base}</p>}
      {note && <p className="text-xs text-amber-700">{note}</p>}
      {children}
    </section>
  );
}
