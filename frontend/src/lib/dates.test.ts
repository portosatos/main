import { addDays, isIsoDate, isIsoWeek, isoWeek, shiftWeek, weekMonday } from "./dates";

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

test("weekMonday, shiftWeek and addDays cross year edges", () => {
  expect(weekMonday("2026-W41")).toBe("2026-10-05");
  expect(weekMonday("2026-W01")).toBe("2025-12-29");
  expect(weekMonday("2026-W53")).toBe("2026-12-28");
  expect(weekMonday("2027-W01")).toBe("2027-01-04");
  expect(shiftWeek("2026-W53", 1)).toBe("2027-W01");
  expect(shiftWeek("2026-W01", -1)).toBe("2025-W52");
  expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
  expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
});

test("URL parameters are checked before use", () => {
  expect(isIsoDate("2026-10-07")).toBe(true);
  expect(isIsoDate("2026-13-40")).toBe(false);
  expect(isIsoDate("07.10.2026")).toBe(false);
  expect(isIsoDate(null)).toBe(false);
  expect(isIsoWeek("2026-W41")).toBe(true);
  expect(isIsoWeek("2026-w41")).toBe(false);
});
