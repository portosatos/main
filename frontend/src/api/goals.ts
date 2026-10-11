import type { GoalKind } from "./summary";

// /api/goals (SPEC F8, §6.3, ADR-043): the targets in effect now; PUT makes a new version.

export type Goal = {
  kind: GoalKind;
  // Steps a day, or hours of sleep.
  target: number;
  // When the target was set; null for the default (8000 steps, 8 h).
  valid_from: string | null;
};

export type GoalsInput = { steps: number; sleep: number };
