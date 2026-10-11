import { useQueryClient, type QueryClient, type QueryKey } from "@tanstack/react-query";
import { useEffect } from "react";

import { meQueryKey } from "@/api/auth";
import type { IngestEvent, IngestJob } from "@/api/ingest";
import { isoWeek } from "@/lib/dates";
import { devicesKey, ingestJobsKey, summaryKeys } from "@/lib/queryKeys";

// The tab's subscription to GET /api/events (SPEC F12, ADR-039, docs/API.md): each event marks
// the queries it changes as stale, and the active ones are fetched again.

// When the browser gives up on the stream (503, 401), the hook reconnects itself with a backoff.
const RETRY_MIN_MS = 1000;
const RETRY_MAX_MS = 30_000;

type Handler = (queryClient: QueryClient, data: unknown) => void;

const handlers: Record<string, Handler> = {
  "summary.updated": (queryClient, data) => {
    const dates = (data as { dates: string[] }).dates;
    void queryClient.invalidateQueries({
      queryKey: summaryKeys.all,
      predicate: (query) => summaryTouched(query.queryKey, dates),
    });
  },
  "ingest.progress": (queryClient, data) => {
    // Progress of a job the tab knows goes straight into the list; a new one needs the list.
    if (!patchJob(queryClient, data as IngestEvent)) {
      void queryClient.invalidateQueries({ queryKey: ingestJobsKey });
    }
  },
  "ingest.done": (queryClient, data) => {
    patchJob(queryClient, data as IngestEvent);
    // The final report (errors, times) and the devices the file brought.
    void queryClient.invalidateQueries({ queryKey: ingestJobsKey });
    void queryClient.invalidateQueries({ queryKey: devicesKey });
  },
};

// Keys of summaryKeys: a day, an ISO week or a range that contains one of the dates.
// Any other summary query is refetched to be safe.
function summaryTouched(key: QueryKey, dates: string[]): boolean {
  const [, kind, first, last] = key as [string, string?, string?, string?];
  if (kind === "day") return dates.includes(first ?? "");
  if (kind === "week") return dates.some((date) => isoWeek(date) === first);
  if (kind === "range") return dates.some((date) => date >= (first ?? "") && date <= (last ?? ""));
  return true;
}

function patchJob(queryClient: QueryClient, event: IngestEvent): boolean {
  const jobs = queryClient.getQueryData<IngestJob[]>(ingestJobsKey);
  if (!jobs?.some((job) => job.id === event.job_id)) return false;
  queryClient.setQueryData<IngestJob[]>(ingestJobsKey, (old) =>
    old?.map((job) =>
      job.id === event.job_id
        ? {
            ...job,
            status: event.status,
            bytes_done: event.bytes_done,
            bytes_total: event.bytes_total,
            progress: event.bytes_total
              ? Math.min(event.bytes_done / event.bytes_total, 1)
              : Number(event.status === "done"),
            counts: { ...job.counts, ...event.counts },
          }
        : job,
    ),
  );
  return true;
}

function parse(data: unknown): unknown {
  try {
    return JSON.parse(String(data));
  } catch {
    return {};
  }
}

export function useEvents(): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    // Not in the browser (jsdom without a fake): no live updates.
    if (typeof EventSource === "undefined") return;

    let source: EventSource | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let retryMs = RETRY_MIN_MS;
    // A `ready` after the first one means a new stream: events may have been missed meanwhile.
    let seenReady = false;
    const refetchAll = () => void queryClient.invalidateQueries();

    const connect = () => {
      const current = new EventSource("/api/events", { withCredentials: true });
      source = current;
      current.addEventListener("ready", () => {
        retryMs = RETRY_MIN_MS;
        if (seenReady) refetchAll();
        seenReady = true;
      });
      current.addEventListener("resync", refetchAll);
      for (const [type, handle] of Object.entries(handlers)) {
        current.addEventListener(type, (event) =>
          handle(queryClient, parse((event as MessageEvent).data)),
        );
      }
      current.addEventListener("error", () => {
        // CONNECTING: the browser reconnects by itself.
        if (current.readyState !== EventSource.CLOSED) return;
        current.close();
        // The session may be gone: /api/auth/me → 401 takes the tab to /login.
        void queryClient.invalidateQueries({ queryKey: meQueryKey });
        retryTimer = setTimeout(connect, retryMs);
        retryMs = Math.min(retryMs * 2, RETRY_MAX_MS);
      });
    };

    connect();
    return () => {
      clearTimeout(retryTimer);
      source?.close();
    };
  }, [queryClient]);
}
