import { addDays } from "./lib/dates";
import { genFixture } from "./lib/htgen";
import { ingestJobs, waitJobDone } from "./lib/ingest";
import { newUser } from "./lib/users";
import { expect, test } from "./test";

// SPEC §8 stage 12, scenario 2 (§9 #6, #7): while a file is processed the progress bar moves, the
// user can open another page, and the summary shows up before the processing ends.

test("загрузка: прогресс меняется, можно уйти на другую страницу, сводка раньше ingest.done", async ({
  page,
}) => {
  const user = await newUser(page);
  // Ten days (~170 thousand records) take the worker several seconds; records go in time order,
  // so the first date of the file is summarised first.
  const first = addDays(user.today, -10);
  const file = genFixture({ end: addDays(user.today, -1), days: 10, seed: 21 });

  await page.goto("/upload");
  await page.getByLabel("Выберите файл NDJSON").setInputFiles(file);

  // The processing bar moves: it takes at least two values, one of them strictly inside 0..100.
  const bar = page.getByRole("progressbar", { name: "Обработка" });
  const seen = new Set<number>();
  await expect
    .poll(
      async () => {
        const value = await bar.getAttribute("aria-valuenow", { timeout: 1_000 }).catch(() => null);
        if (value !== null) seen.add(Number(value));
        return seen.size >= 2 && [...seen].some((v) => v > 0 && v < 100);
      },
      { timeout: 60_000, intervals: [100] },
    )
    .toBe(true);
  const [job] = await ingestJobs(page);
  expect(job.status).toBe("processing");

  // Another page opens while the file is processed (SPA navigation, the tab is responsive).
  await page.getByRole("navigation", { name: "Разделы" }).getByRole("link", { name: "Дашборд" }).click();
  await expect(page.getByRole("heading", { name: "Дашборд" })).toBeVisible({ timeout: 2_000 });
  await page.getByLabel("Дата").fill(first);
  await expect(page).toHaveURL(new RegExp(`date=${first}$`));

  // The steps of the first date appear (summary.updated) while the job is still running.
  const steps = page.getByRole("region", { name: "Шаги", exact: true });
  await expect(steps.getByText(/^\d[\d\s]*$/)).toBeVisible({ timeout: 60_000 });
  const [during] = await ingestJobs(page);
  expect(during.id).toBe(job.id);
  expect(during.status, "the summary appeared only after ingest.done").toBe("processing");

  // The job finishes, and the summary stays.
  const done = await waitJobDone(page, job.id);
  expect(done.counts.new).toBe(done.counts.total);
  await expect(steps.getByText(/^\d[\d\s]*$/)).toBeVisible();
});
