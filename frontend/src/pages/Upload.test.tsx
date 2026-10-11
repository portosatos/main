import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import type { IngestJob } from "@/api/ingest";
import { useEvents } from "@/hooks/useEvents";
import { FakeEventSource, installFakeEventSource } from "@/test/fakeEventSource";
import { FakeXhr, installFakeXhr } from "@/test/fakeXhr";
import { renderRoutes } from "@/test/render";
import { server } from "@/test/server";

import Upload from "./Upload";

const JOB_ID = "0b6f2c1e-6a43-4c1d-9a0f-3e2b7c5d9a10";

function makeJob(overrides: Partial<IngestJob> = {}): IngestJob {
  return {
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
    ...overrides,
  };
}

// In the app useEvents runs in the layout; here next to the page.
function UploadWithEvents() {
  useEvents();
  return <Upload />;
}

function renderUpload() {
  return renderRoutes([{ path: "/upload", element: <UploadWithEvents /> }], ["/upload"]);
}

function bar(name: string) {
  return screen.getByRole("progressbar", { name });
}

beforeEach(() => {
  installFakeEventSource();
  installFakeXhr();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test.fails("upload bar follows XHR progress", async () => {
  server.use(http.get("/api/ingest/jobs", () => HttpResponse.json([])));
  const user = userEvent.setup();
  renderUpload();

  const file = new File(['{"type":"steps"}\n'], "month.ndjson", { type: "application/x-ndjson" });
  await user.upload(await screen.findByLabelText(/Выберите файл/), file);

  const xhr = FakeXhr.last;
  expect(xhr.method).toBe("POST");
  expect(xhr.url).toMatch(/\/api\/ingest\/files$/);
  expect(xhr.headers["X-Requested-With"]).toBe("ht");
  expect(xhr.withCredentials).toBe(true);
  expect((xhr.body as FormData).get("file")).toBe(file);
  expect(bar("Передача файла")).toHaveAttribute("aria-valuenow", "0");

  xhr.progress(250, 1000);
  expect(bar("Передача файла")).toHaveAttribute("aria-valuenow", "25");
  xhr.progress(1000, 1000);
  expect(bar("Передача файла")).toHaveAttribute("aria-valuenow", "100");

  xhr.respond(202, { job_id: JOB_ID });
  expect(await screen.findByText(/Файл передан/)).toBeInTheDocument();
});

test.fails("processing bar follows ingest.progress", async () => {
  let job = makeJob();
  server.use(http.get("/api/ingest/jobs", () => HttpResponse.json([job])));
  renderUpload();

  // A job of this user that is already running (e.g. uploaded in another tab).
  await waitFor(() => expect(bar("Обработка")).toHaveAttribute("aria-valuenow", "0"));
  const source = FakeEventSource.last;
  source.emit("ready");

  const counts = { new: 300, duplicate: 0, conflict: 0, invalid: 0 };
  source.emit("ingest.progress", {
    job_id: JOB_ID,
    status: "processing",
    bytes_done: 300,
    bytes_total: 1000,
    counts,
  });
  expect(bar("Обработка")).toHaveAttribute("aria-valuenow", "30");

  job = makeJob({
    status: "done",
    bytes_done: 1000,
    progress: 1,
    counts: { total: 900, new: 900, duplicate: 0, conflict: 0, invalid: 0 },
    finished_at: "2026-10-11T04:00:30Z",
  });
  source.emit("ingest.done", {
    job_id: JOB_ID,
    status: "done",
    bytes_done: 1000,
    bytes_total: 1000,
    counts,
  });
  await waitFor(() => expect(bar("Обработка")).toHaveAttribute("aria-valuenow", "100"));
  const processing = screen.getByRole("region", { name: "Обработка" });
  expect(within(processing).getByText("Готово")).toBeInTheDocument();
});

test.fails("history shows new/duplicate/conflict/invalid and expandable errors", async () => {
  server.use(
    http.get("/api/ingest/jobs", () =>
      HttpResponse.json([
        makeJob({
          status: "done",
          bytes_done: 1000,
          progress: 1,
          counts: { total: 1000, new: 700, duplicate: 200, conflict: 60, invalid: 40 },
          errors: [
            { line: 3, kind: "invalid", reason: "нет поля start" },
            { line: 17, kind: "conflict", reason: "другое значение шагов" },
          ],
          finished_at: "2026-10-11T04:00:30Z",
        }),
        makeJob({ id: "second-job", filename: "empty.ndjson", status: "failed" }),
      ]),
    ),
  );
  const user = userEvent.setup();
  renderUpload();

  const history = await screen.findByRole("table", { name: "История загрузок" });
  const row = within(history).getByRole("row", { name: /week\.ndjson/ });
  for (const value of ["1000", "700", "200", "60", "40", "Готово"]) {
    expect(within(row).getByRole("cell", { name: value })).toBeInTheDocument();
  }
  expect(within(history).getByRole("row", { name: /empty\.ndjson/ })).toHaveTextContent("Ошибка");

  expect(screen.queryByText(/нет поля start/)).not.toBeInTheDocument();
  await user.click(within(row).getByRole("button", { name: "Ошибки (2)" }));
  expect(await screen.findByText(/Строка 3/)).toHaveTextContent("нет поля start");
  expect(screen.getByText(/Строка 17/)).toHaveTextContent("другое значение шагов");
});
