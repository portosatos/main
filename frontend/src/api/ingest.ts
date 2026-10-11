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
