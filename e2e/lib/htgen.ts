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

// Writes an NDJSON file with htgen (docs/DATA_FORMAT.md) and returns its absolute path.
export function genFixture(options: FixtureOptions): string {
  void options;
  throw new Error("step 12.1: not implemented");
}
