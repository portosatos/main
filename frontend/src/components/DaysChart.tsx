import { useId } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import GapBar, { GapPattern, type ChartDay, type GapBarProps } from "@/components/GapBar";
import { formatDay, formatTick } from "@/lib/dates";

// Bars of one metric by day (SPEC §6.4, F6): gaps hatched with «нет данных», partial days marked.

type Props = {
  title: string;
  days: ChartDay[];
  format: (value: number) => string;
  // Ticks of the Y axis are multiples of it; also the top when there is no data at all.
  step: number;
  // Fill of the bars, a CSS color.
  color: string;
  className?: string;
};

type Row = ChartDay & { label: string; bar: number };

export default function DaysChart({ title, days, format, step, color, className }: Props) {
  const patternId = `gap-${useId().replace(/:/g, "")}`;
  const values = days.flatMap((day) => (day.value === null ? [] : [day.value]));
  // At most 4 intervals on the Y axis, each a multiple of `step`.
  const tick = Math.max(1, Math.ceil(Math.max(0, ...values) / step / 4)) * step;
  const top = Math.max(tick, Math.ceil(Math.max(0, ...values) / tick) * tick);
  const ticks = Array.from({ length: top / tick + 1 }, (_, i) => i * tick);
  // A gap is drawn over the whole column, so it gets the top as its height.
  const rows: Row[] = days.map((day) => ({ ...day, label: formatTick(day.date), bar: day.value ?? top }));

  return (
    <figure className={`min-w-0 ${className ?? ""}`}>
      <figcaption className="mb-2 text-sm font-medium">{title}</figcaption>
      <ResponsiveContainer width="100%" height={200} initialDimension={{ width: 320, height: 200 }}>
        <BarChart data={rows} margin={{ top: 16, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <GapPattern id={patternId} />
          </defs>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="label" tickLine={false} interval={0} fontSize={11} />
          <YAxis
            domain={[0, top]}
            ticks={ticks}
            width={44}
            fontSize={11}
            tickLine={false}
            tickFormatter={(value: number) => format(value)}
          />
          <Tooltip
            cursor={{ className: "fill-muted/60" }}
            content={({ active, payload }) => {
              const day = active ? (payload?.[0]?.payload as Row | undefined) : undefined;
              if (!day) return null;
              return (
                <div className="rounded-md border bg-background px-2 py-1 text-xs shadow">
                  <div className="font-medium">{formatDay(day.date)}</div>
                  <div>
                    {day.value === null ? "нет данных" : format(day.value)}
                    {day.status === "partial" && " · неполные данные"}
                  </div>
                </div>
              );
            }}
          />
          <Bar
            dataKey="bar"
            isAnimationActive={false}
            shape={(props: unknown) => (
              <GapBar {...(props as GapBarProps)} patternId={patternId} fill={color} />
            )}
          />
        </BarChart>
      </ResponsiveContainer>
    </figure>
  );
}
