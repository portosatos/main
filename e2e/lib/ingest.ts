import type { Page } from "@playwright/test";

export type IngestCounts = {
  total: number;
  new: number;
  duplicate: number;
  conflict: number;
  invalid: number;
};

export type IngestJob = {
  id: string;
  filename: string | null;
  status: "queued" | "processing" | "done" | "failed";
  counts: IngestCounts;
};

// The user's jobs, newest first (`GET /api/ingest/jobs`, the page's session).
export async function ingestJobs(page: Page): Promise<IngestJob[]> {
  void page;
  throw new Error("step 12.1: not implemented");
}

// Uploads a file through the API (`POST /api/ingest/files`) and waits until its job is done.
export async function uploadAndWait(page: Page, file: string): Promise<IngestJob> {
  void page;
  void file;
  throw new Error("step 12.1: not implemented");
}

// Waits until the job is `done`; `failed` fails the test at once.
export async function waitJobDone(page: Page, jobId: string): Promise<IngestJob> {
  void page;
  void jobId;
  throw new Error("step 12.1: not implemented");
}
