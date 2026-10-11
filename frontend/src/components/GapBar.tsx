import type { DayStatus } from "@/api/summary";

// One day of a bar chart (a Recharts bar shape): a day without data is a hatched gap, not zero
// (SPEC F6). Implemented in step 6.1.

export type ChartDay = { date: string; status: DayStatus; value: number | null };

export type GapBarProps = {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  // The whole column of the day (Recharts passes it to a bar shape).
  background?: { x?: number; y?: number; width?: number; height?: number };
  payload?: ChartDay;
  // Id of the chart's hatch <pattern>.
  patternId: string;
};

export default function GapBar(props: GapBarProps) {
  void props;
  return null;
}
