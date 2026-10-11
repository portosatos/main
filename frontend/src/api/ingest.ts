import { useQuery } from "@tanstack/react-query";

import { ingestJobsKey } from "@/lib/queryKeys";

import { api, ApiError, onUnauthorized } from "./client";

// /api/ingest/* (SPEC F3, §6.3): file upload and the reports of the user's jobs.

export type IngestStatus = "queued" | "processing" | "done" | "failed";

export type IngestCounts = {
  total: number;
  new: number;
  duplicate: number;
  conflict: number;
  invalid: number;
};

export type IngestError = { line: number; kind: "invalid" | "conflict"; reason: string };

export type IngestJob = {
  id: string;
  source: "file" | "stream";
  filename: string | null;
  status: IngestStatus;
  bytes_total: number;
  bytes_done: number;
  progress: number;
  counts: IngestCounts;
  errors: IngestError[];
  warnings: string[];
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

// Data of `ingest.progress` and `ingest.done` (docs/API.md, ADR-039).
export type IngestEvent = {
  job_id: string;
  status: IngestStatus;
  bytes_done: number;
  bytes_total: number;
  counts: Omit<IngestCounts, "total">;
};

export type UploadAccepted = { job_id: string };

export function useIngestJobs() {
  return useQuery({
    queryKey: ingestJobsKey,
    queryFn: () => api.get<IngestJob[]>("/api/ingest/jobs"),
  });
}

// fetch has no upload progress, XMLHttpRequest does (SPEC §6.4): the file goes as multipart
// field `file`, with the session cookie and the CSRF header like every other mutating request.
export function sendFile(
  file: File,
  onProgress: (loaded: number, total: number) => void,
): Promise<UploadAccepted> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/ingest/files");
    xhr.withCredentials = true;
    xhr.setRequestHeader("Accept", "application/json");
    xhr.setRequestHeader("X-Requested-With", "ht");
    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) onProgress(event.loaded, event.total);
    });
    xhr.addEventListener("load", () => {
      const body = parseBody(xhr.responseText);
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as UploadAccepted);
        return;
      }
      if (xhr.status === 401) onUnauthorized();
      const detail = body !== null && typeof body === "object" && "detail" in body ? body.detail : body;
      reject(new ApiError(xhr.status, detail));
    });
    xhr.addEventListener("error", () => reject(new Error("network")));
    xhr.addEventListener("abort", () => reject(new Error("aborted")));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

function parseBody(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}
