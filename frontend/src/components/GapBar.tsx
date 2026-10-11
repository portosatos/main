import type { DayStatus } from "@/api/summary";

// One day of a bar chart (a Recharts bar shape). A day without data is a hatched gap over the
// whole column with «нет данных», not a bar of height 0 (SPEC F6); a partial day is a paler bar
// marked «неполн.».

export type ChartDay = { date: string; status: DayStatus; value: number | null };

type Rect = { x?: number; y?: number; width?: number; height?: number };

export type GapBarProps = Rect & {
  // The whole column of the day (Recharts passes it to a bar shape).
  background?: Rect;
  payload?: ChartDay;
  // Id of the chart's hatch <pattern> (see GapPattern).
  patternId: string;
  fill?: string;
};

export default function GapBar({
  background,
  payload,
  patternId,
  fill = "currentColor",
  ...bar
}: GapBarProps) {
  if (!payload) return null;
  const { x = 0, y = 0, width = 0, height = 0 } = payload.value === null ? (background ?? bar) : bar;
  const middle = x + width / 2;

  if (payload.value === null) {
    return (
      <g data-gap="no_data">
        <title>нет данных</title>
        <rect x={x} y={y} width={width} height={height} fill={`url(#${patternId})`} />
        <text
          x={middle}
          y={y + height / 2}
          transform={`rotate(-90 ${middle} ${y + height / 2})`}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={11}
          className="fill-muted-foreground"
        >
          нет данных
        </text>
      </g>
    );
  }

  const partial = payload.status === "partial";
  return (
    <g data-gap={partial ? "partial" : undefined}>
      {partial && <title>неполные данные</title>}
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        rx={2}
        fill={fill}
        fillOpacity={partial ? 0.4 : 1}
      />
      {partial && (
        // Short: a column is ~35 px wide at 375 px; the chart's legend spells it out.
        <text x={middle} y={y - 4} textAnchor="middle" fontSize={9} className="fill-muted-foreground">
          неполн.
        </text>
      )}
    </g>
  );
}

// The hatch of the gaps; one per chart, inside its <defs>.
export function GapPattern({ id }: { id: string }) {
  return (
    <pattern id={id} width={6} height={6} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width={6} height={6} className="fill-muted" />
      <line x1={0} y1={0} x2={0} y2={6} strokeWidth={2} className="stroke-muted-foreground/40" />
    </pattern>
  );
}
