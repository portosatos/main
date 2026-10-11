import { useSyncExternalStore } from "react";
import type { QueryClient } from "@tanstack/react-query";

import { errorMessage } from "@/api/auth";
import { sendFile } from "@/api/ingest";
import { ingestJobsKey } from "@/lib/queryKeys";

// The tab's file transfer lives outside the page: the user may open other pages while a large
// file is sent and see the bar again on return (SPEC §4, "интерфейс отзывчив").
export type Transfer = {
  fileName: string;
  loaded: number;
  total: number;
  status: "sending" | "sent" | "failed";
  jobId?: string;
  error?: string;
};

let transfer: Transfer | null = null;
const listeners = new Set<() => void>();

function update(next: Transfer): void {
  transfer = next;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useTransfer(): Transfer | null {
  return useSyncExternalStore(subscribe, () => transfer);
}

export async function startTransfer(file: File, queryClient: QueryClient): Promise<void> {
  let current: Transfer = { fileName: file.name, loaded: 0, total: file.size, status: "sending" };
  update(current);
  try {
    const { job_id } = await sendFile(file, (loaded, total) => {
      current = { ...current, loaded, total };
      update(current);
    });
    update({ ...current, loaded: current.total, status: "sent", jobId: job_id });
    void queryClient.invalidateQueries({ queryKey: ingestJobsKey });
  } catch (error) {
    update({ ...current, status: "failed", error: errorMessage(error, "Не удалось загрузить файл") });
  }
}
