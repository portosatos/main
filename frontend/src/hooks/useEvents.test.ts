import { QueryClient, QueryClientProvider, type QueryKey } from "@tanstack/react-query";
import { renderHook } from "@testing-library/react";
import { createElement, type ReactNode } from "react";

import type { IngestJob } from "@/api/ingest";
import { devicesKey, ingestJobsKey, summaryKeys } from "@/lib/queryKeys";
import { FakeEventSource, installFakeEventSource } from "@/test/fakeEventSource";

import { useEvents } from "./useEvents";

const JOB_ID = "0b6f2c1e-6a43-4c1d-9a0f-3e2b7c5d9a10";

const job: IngestJob = {
  id: JOB_ID,
  source: "file",
  filename: "week.ndjson",
  status: "processing",
  bytes_total: 1000,
  bytes_done: 0,
  progress: 0,
  counts: { total: 0, new: 0, duplicate: 0, conflict: 0, invalid: 0 },
  errors: [],
  warnings: [],
  created_at: "2026-10-11T04:00:00Z",
  started_at: "2026-10-11T04:00:01Z",
  finished_at: null,
};

// Every key a test looks at is in the cache (inactive, so nothing is fetched).
const keys: Record<string, QueryKey> = {
  me: ["auth", "me"],
  jobs: ingestJobsKey,
  devices: devicesKey,
  day07: summaryKeys.day("2026-10-07"),
  day01: summaryKeys.day("2026-10-01"),
  week41: summaryKeys.week("2026-W41"),
  week40: summaryKeys.week("2026-W40"),
  rangeOct: summaryKeys.range("2026-10-01", "2026-10-31"),
  rangeSep: summaryKeys.range("2026-09-01", "2026-09-30"),
  goals: ["goals"],
  notifications: ["notifications"],
};

function setup() {
  installFakeEventSource();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  for (const [name, key] of Object.entries(keys)) {
    queryClient.setQueryData(key, name === "jobs" ? [job] : { name });
  }
  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
  renderHook(() => useEvents(), { wrapper });
  return queryClient;
}

function invalidated(queryClient: QueryClient): string[] {
  return Object.entries(keys)
    .filter(([, key]) => queryClient.getQueryState(key)?.isInvalidated)
    .map(([name]) => name)
    .sort();
}

function reset(queryClient: QueryClient): void {
  for (const [name, key] of Object.entries(keys)) {
    queryClient.setQueryData(key, queryClient.getQueryData(key) ?? { name });
  }
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("maps each event type to invalidated query keys", () => {
  const queryClient = setup();
  const source = FakeEventSource.last;
  expect(source.url).toMatch(/\/api\/events$/);
  expect(source.withCredentials).toBe(true);

  // The first `ready` of the tab: nothing to catch up on.
  source.emit("ready");
  expect(invalidated(queryClient)).toEqual([]);

  // Summaries of the given local dates: the day, its ISO week and ranges that contain it.
  source.emit("summary.updated", { dates: ["2026-10-07"] });
  expect(invalidated(queryClient)).toEqual(["day07", "rangeOct", "week41"]);
  reset(queryClient);

  // Progress of a known job is written into the cached list, without a request.
  const progress = {
    job_id: JOB_ID,
    status: "processing",
    bytes_done: 400,
    bytes_total: 1000,
    counts: { new: 10, duplicate: 2, conflict: 1, invalid: 0 },
  };
  source.emit("ingest.progress", progress);
  expect(invalidated(queryClient)).toEqual([]);
  const [cached] = queryClient.getQueryData<IngestJob[]>(ingestJobsKey) ?? [];
  expect(cached).toMatchObject({
    status: "processing",
    bytes_done: 400,
    progress: 0.4,
    counts: { new: 10, duplicate: 2, conflict: 1, invalid: 0 },
  });

  // A job the tab has not seen (uploaded in another tab): the list is fetched again.
  source.emit("ingest.progress", { ...progress, job_id: "another-job" });
  expect(invalidated(queryClient)).toEqual(["jobs"]);
  reset(queryClient);

  // The job is over: the final report (errors, times) and the devices it brought.
  source.emit("ingest.done", { ...progress, status: "done", bytes_done: 1000 });
  expect(invalidated(queryClient)).toEqual(["devices", "jobs"]);
});

test("refetches everything after reconnect", () => {
  vi.useFakeTimers();
  const queryClient = setup();
  const first = FakeEventSource.last;
  first.emit("ready");

  // The browser reconnected by itself: the new `ready` means events may have been missed.
  first.fail(FakeEventSource.CONNECTING);
  expect(invalidated(queryClient)).toEqual([]);
  first.emit("ready");
  expect(invalidated(queryClient)).toEqual(Object.keys(keys).sort());
  reset(queryClient);

  // The API lost its LISTEN connection to the database.
  first.emit("resync");
  expect(invalidated(queryClient)).toEqual(Object.keys(keys).sort());
  reset(queryClient);

  // The browser gave up (e.g. 503): the hook opens a new stream itself, and catches up on `ready`.
  first.fail(FakeEventSource.CLOSED);
  vi.advanceTimersByTime(30_000);
  expect(FakeEventSource.instances).toHaveLength(2);
  const second = FakeEventSource.last;
  expect(first.readyState).toBe(FakeEventSource.CLOSED);
  second.emit("ready");
  expect(invalidated(queryClient)).toEqual(Object.keys(keys).sort());
});

test("devices.changed invalidates the device list", () => {
  const queryClient = setup();
  const source = FakeEventSource.last;
  source.emit("ready");

  // A device was renamed in another tab (SPEC F12): only the device list is fetched again.
  source.emit("devices.changed", { device_id: "5d1f4c1e-0000-4000-8000-000000000001" });
  expect(invalidated(queryClient)).toEqual(["devices"]);
});

test("goal and notification events invalidate their keys", () => {
  const queryClient = setup();
  const source = FakeEventSource.last;
  source.emit("ready");

  // Goals changed in another tab: the form and the progress of every summary (SPEC F8).
  source.emit("goal.changed", { kinds: ["steps"] });
  expect(invalidated(queryClient)).toEqual(
    ["day01", "day07", "goals", "rangeOct", "rangeSep", "week40", "week41"].sort(),
  );
  reset(queryClient);

  // The bell: a new notification, then read in another tab.
  source.emit("notification.created", { id: "n1", type: "goal.achieved" });
  expect(invalidated(queryClient)).toEqual(["notifications"]);
  reset(queryClient);
  source.emit("notifications.read", { all: true });
  expect(invalidated(queryClient)).toEqual(["notifications"]);
  reset(queryClient);

  // goal.achieved only shows a toast: its data come with summary.updated and notification.created.
  source.emit("goal.achieved", {
    kind: "steps",
    local_date: "2026-09-01",
    target: 8000,
    value: 9000,
    show_toast: false,
    notification_id: "n1",
  });
  expect(invalidated(queryClient)).toEqual([]);
});
