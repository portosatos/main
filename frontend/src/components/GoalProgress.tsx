import type { GoalKind, GoalProgress as Progress } from "@/api/summary";

export type GoalProgressProps = { kind: GoalKind; progress: Progress };

// Progress of a day's goal (SPEC F8): the share of the target as a bar and in words.
// Step 7.2 stub: the interface the tests use, nothing is shown yet.
export default function GoalProgress(props: GoalProgressProps) {
  void props;
  return null;
}
