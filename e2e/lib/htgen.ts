import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, renameSync } from "node:fs";
import path from "node:path";

import { REPO_ROOT } from "./env";

export type FixtureOptions = {
  // The last local date of the file (YYYY-MM-DD) and the number of days.
  end: string;
  days: number;
  seed: number;
  // htgen --scenario, e.g. "short-sleep".
  scenario?: string;
  // htgen --gap values, e.g. "2026-10-03T00:00/2026-10-04T00:00" (all devices).
  gaps?: string[];
};

const FIXTURES_DIR = path.join(REPO_ROOT, "e2e", ".fixtures");

// Writes an NDJSON file with htgen (docs/DATA_FORMAT.md) and returns its absolute path. htgen is
// deterministic, so a file with the same arguments is reused (the name carries all of them).
export function genFixture(options: FixtureOptions): string {
  const args = ["--end", options.end, "--days", String(options.days), "--seed", String(options.seed)];
  if (options.scenario) args.push("--scenario", options.scenario);
  for (const gap of options.gaps ?? []) args.push("--gap", gap);

  const parts = [`d${options.days}`, options.end, `s${options.seed}`, options.scenario, ...(options.gaps ?? [])];
  const name = parts
    .filter(Boolean)
    .join("_")
    .replace(/[^\w-]+/g, "-");
  const file = path.join(FIXTURES_DIR, `${name}.ndjson`);
  if (existsSync(file)) return file;

  mkdirSync(FIXTURES_DIR, { recursive: true });
  const partial = `${file}.part`;
  execFileSync("uv", ["run", "--project", path.join(REPO_ROOT, "generator"), "htgen", ...args, "--out", partial], {
    cwd: REPO_ROOT,
    stdio: ["ignore", "ignore", "pipe"],
  });
  renameSync(partial, file);
  return file;
}
