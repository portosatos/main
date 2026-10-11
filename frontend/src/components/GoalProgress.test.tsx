import { render, screen } from "@testing-library/react";

import GoalProgress from "./GoalProgress";

// Progress of a day's goal on the dashboard (SPEC F8): value as a percent of the target in effect
// that day — a bar and words; the percent comes from the API (rounded down, may pass 100).

test("shows percent of target", () => {
  const { rerender } = render(
    <GoalProgress kind="steps" progress={{ target: 8000, percent: 75, achieved: false }} />,
  );
  const bar = screen.getByRole("progressbar", { name: "Цель по шагам" });
  expect(bar).toHaveAttribute("aria-valuenow", "75");
  expect(screen.getByText("75 % от цели 8 000 шагов")).toBeInTheDocument();
  expect(screen.queryByText(/цель выполнена/)).not.toBeInTheDocument();

  // Over the target: the bar is full, the words keep the real percent.
  rerender(<GoalProgress kind="sleep" progress={{ target: 7.5, percent: 116, achieved: true }} />);
  const sleepBar = screen.getByRole("progressbar", { name: "Цель по сну" });
  expect(sleepBar).toHaveAttribute("aria-valuenow", "100");
  expect(screen.getByText("116 % от цели 7,5 ч")).toBeInTheDocument();
  expect(screen.getByText("цель выполнена")).toBeInTheDocument();

  // No value that day: no bar and no «0 %» (SPEC F6), only the target.
  rerender(<GoalProgress kind="steps" progress={{ target: 8000, percent: null, achieved: false }} />);
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  expect(screen.getByText("цель — 8 000 шагов")).toBeInTheDocument();
  expect(screen.queryByText(/0 %/)).not.toBeInTheDocument();
});
