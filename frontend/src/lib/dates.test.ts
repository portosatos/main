import { isoWeek } from "./dates";

test("isoWeek handles year edges", () => {
  expect(isoWeek("2026-10-07")).toBe("2026-W41");
  expect(isoWeek("2026-10-11")).toBe("2026-W41");
  expect(isoWeek("2026-10-12")).toBe("2026-W42");
  // 29.12.2025 is Monday of 2026-W01; 2026 has 53 weeks, its last one ends on 03.01.2027.
  expect(isoWeek("2025-12-29")).toBe("2026-W01");
  expect(isoWeek("2025-12-28")).toBe("2025-W52");
  expect(isoWeek("2026-12-31")).toBe("2026-W53");
  expect(isoWeek("2027-01-03")).toBe("2026-W53");
  expect(isoWeek("2027-01-04")).toBe("2027-W01");
});
