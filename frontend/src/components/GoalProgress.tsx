import type { GoalKind, GoalProgress as Progress } from "@/api/summary";
import ProgressBar from "@/components/ProgressBar";
import { formatGoalAmount, GOAL_TITLES } from "@/lib/metrics";

export type GoalProgressProps = { kind: GoalKind; progress: Progress };

// Progress of a day's goal (SPEC F8): the share of the target in effect that day as a bar and in
// words. The percent is the API's (rounded down, 100 only when met) and may pass 100; a day
// without a value shows only the target, never «0 %» (SPEC F6).
export default function GoalProgress({ kind, progress }: GoalProgressProps) {
  const { target, percent, achieved } = progress;
  if (percent === null) {
    return <p className="text-xs text-muted-foreground">цель — {formatGoalAmount(kind, target)}</p>;
  }
  return (
    <div className="mt-1 grid gap-1">
      <ProgressBar label={GOAL_TITLES[kind]} value={percent} />
      <p className="text-xs text-muted-foreground">
        <span>
          {percent} % от цели {formatGoalAmount(kind, target)}
        </span>
        {achieved && (
          <>
            {" · "}
            <span className="font-medium text-emerald-700">цель выполнена</span>
          </>
        )}
      </p>
    </div>
  );
}
