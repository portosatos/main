import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import type { Rule } from "@/api/rules";
import { renderRoutes } from "@/test/render";
import { server } from "@/test/server";

import Rules from "./Rules";

// The rules page (SPEC §6.4, F9): a card per rule — title, description, thresholds, switch.

const R1: Rule = {
  code: "R1",
  title: "Недосып",
  description: "Три валидные ночи подряд, в каждой меньше 6 ч сна.",
  params: { nights: 3, short_hours: 6, close_hours: 7 },
  enabled: true,
  changed_at: null,
};

const R2: Rule = {
  code: "R2",
  title: "Мало шагов",
  description: "Три полных дня подряд, в каждый меньше половины цели по шагам.",
  params: { days: 3, goal_share: 0.5 },
  enabled: false,
  changed_at: "2026-10-10T06:00:00Z",
};

test("toggle calls API and reflects state", async () => {
  let rules = [R1, R2];
  const patches: { code: string; body: unknown; csrf: string | null }[] = [];
  server.use(
    http.get("/api/rules", () => HttpResponse.json(rules)),
    http.patch("/api/rules/:code", async ({ request, params }) => {
      const body = (await request.json()) as { enabled: boolean };
      patches.push({ code: String(params.code), body, csrf: request.headers.get("X-Requested-With") });
      rules = rules.map((r) => (r.code === params.code ? { ...r, enabled: body.enabled } : r));
      return HttpResponse.json(rules.find((r) => r.code === params.code));
    }),
  );
  const user = userEvent.setup();
  renderRoutes([{ path: "/rules", element: <Rules /> }], ["/rules"]);

  const r1 = await screen.findByRole("article", { name: "R1 Недосып" });
  expect(within(r1).getByText(R1.description)).toBeInTheDocument();
  // The thresholds in words, one per parameter.
  const thresholds = within(r1).getByRole("list", { name: "Пороги" });
  expect(within(thresholds).getAllByRole("listitem")).toHaveLength(3);
  expect(thresholds).toHaveTextContent("Ночей подряд: 3");
  expect(thresholds).toHaveTextContent("Короткая ночь: меньше 6 ч");
  const r2 = screen.getByRole("article", { name: "R2 Мало шагов" });
  expect(within(r2).getByRole("list", { name: "Пороги" })).toHaveTextContent("50 % цели");

  const r1Switch = within(r1).getByRole("switch", { name: "Правило R1 включено" });
  const r2Switch = within(r2).getByRole("switch", { name: "Правило R2 включено" });
  expect(r1Switch).toBeChecked();
  expect(r2Switch).not.toBeChecked();

  await user.click(r1Switch);
  await waitFor(() => expect(r1Switch).not.toBeChecked());
  await user.click(r2Switch);
  await waitFor(() => expect(r2Switch).toBeChecked());

  expect(patches).toEqual([
    { code: "R1", body: { enabled: false }, csrf: "ht" },
    { code: "R2", body: { enabled: true }, csrf: "ht" },
  ]);
});
