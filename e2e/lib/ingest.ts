import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, type Page } from "@playwright/test";

import { CSRF_HEADERS } from "./env";

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
  const response = await page.request.get("/api/ingest/jobs");
  expect(response.status()).toBe(200);
  return (await response.json()) as IngestJob[];
}

// Uploads a file through the API (`POST /api/ingest/files`) and waits until its job is done.
export async function uploadAndWait(page: Page, file: string): Promise<IngestJob> {
  const response = await page.request.post("/api/ingest/files", {
    headers: CSRF_HEADERS,
    multipart: {
      file: { name: path.basename(file), mimeType: "application/x-ndjson", buffer: readFileSync(file) },
    },
  });
  expect(response.status(), await response.text()).toBe(202);
  const { job_id } = (await response.json()) as { job_id: string };
  return waitJobDone(page, job_id);
}

// Waits until the job is `done`; `failed` fails the test at once.
export async function waitJobDone(page: Page, jobId: string, timeoutMs = 90_000): Promise<IngestJob> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const response = await page.request.get(`/api/ingest/jobs/${jobId}`);
    expect(response.status()).toBe(200);
    const job = (await response.json()) as IngestJob;
    expect(job.status, JSON.stringify(job)).not.toBe("failed");
    if (job.status === "done") return job;
    expect(Date.now(), `job ${jobId} is still ${job.status}`).toBeLessThan(deadline);
    await page.waitForTimeout(250);
  }
}
