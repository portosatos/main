import { render } from "@testing-library/react";

import GapBar, { type GapBarProps } from "./GapBar";

// A bar of the steps or sleep chart (SPEC F6): a day without data is a hatched gap over the whole
// column with the label «нет данных», not a bar of height 0.

const COLUMN = { x: 10, y: 0, width: 30, height: 200 };

function renderBar(props: Omit<GapBarProps, "patternId">) {
  const { container } = render(
    <svg>
      <GapBar patternId="hatch-test" {...props} />
    </svg>,
  );
  return container;
}

test("null value rendered as hatched gap", () => {
  const gap = renderBar({
    x: 10,
    y: 200,
    width: 30,
    height: 0,
    background: COLUMN,
    payload: { date: "2026-10-08", status: "no_data", value: null },
  });
  const hatch = gap.querySelector('rect[fill="url(#hatch-test)"]');
  expect(hatch).not.toBeNull();
  // The whole column, so the gap is seen.
  expect(hatch).toHaveAttribute("height", "200");
  expect(hatch).toHaveAttribute("y", "0");
  expect(gap.querySelector("svg")).toHaveTextContent("нет данных");

  // A day with a value is a plain bar of its height, without the hatch.
  const bar = renderBar({
    x: 10,
    y: 120,
    width: 30,
    height: 80,
    background: COLUMN,
    payload: { date: "2026-10-07", status: "complete", value: 8000 },
  });
  expect(bar.querySelector('rect[fill="url(#hatch-test)"]')).toBeNull();
  expect(bar.querySelector('rect[height="80"]')).not.toBeNull();
  expect(bar.querySelector("svg")).not.toHaveTextContent("нет данных");
});
