import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import type { Feedback, Recommendation } from "@/api/recommendations";
import type { Rule } from "@/api/rules";
import { renderRoutes } from "@/test/render";
import { server } from "@/test/server";

import Recommendations from "./Recommendations";

// The recommendations page (SPEC §6.4, F9): tabs «Активные» and «История», a filter by rule,
// status and the dates of opening and closing, «Полезно» / «Не полезно», the disclaimer.
// Times are at noon UTC, so their dates are the same in the zone the tests run in.

function rule(code: string, title: string): Rule {
  return { code, title, description: `${title}.`, params: {}, enabled: true, changed_at: null };
}

const RULES = [rule("R1", "Недосып"), rule("R2", "Мало шагов"), rule("R3", "Повышенный пульс в покое")];

function rec(
  id: string,
  code: string,
  title: string,
  status: Recommendation["status"],
  opened: string,
  resolved: string | null = null,
  feedback: Feedback | null = null,
): Recommendation {
  return {
    id,
    rule_code: code,
    title,
    status,
    opened_at: `${opened}T12:00:00Z`,
    anchor_date: opened,
    context: {},
    resolved_at: resolved && `${resolved}T12:00:00Z`,
    resolve_reason: { open: null, resolved: "auto", closed_rule_disabled: "rule_disabled" }[status],
    feedback,
    feedback_at: feedback && `${opened}T13:00:00Z`,
  };
}

const ACTIVE = rec("a1", "R1", "Недосып", "open", "2026-10-10", null, "useful");
const AUTO = rec("h1", "R2", "Мало шагов", "resolved", "2026-10-05", "2026-10-08");
const DISABLED = rec("h2", "R3", "Повышенный пульс в покое", "closed_rule_disabled", "2026-10-03", "2026-10-04");

// GET /api/recommendations by its filters: status (repeated) and rule.
function serve(items: () => Recommendation[]) {
  const requests: string[] = [];
  server.use(
    http.get("/api/rules", () => HttpResponse.json(RULES)),
    http.get("/api/recommendations", ({ request }) => {
      const params = new URL(request.url).searchParams;
      requests.push(params.toString());
      const statuses = params.getAll("status");
      const code = params.get("rule");
      return HttpResponse.json(
        items().filter(
          (r) => (!statuses.length || statuses.includes(r.status)) && (!code || r.rule_code === code),
        ),
      );
    }),
  );
  return requests;
}

function renderPage() {
  return renderRoutes([{ path: "/recommendations", element: <Recommendations /> }], ["/recommendations"]);
}

test("active and history tabs", async () => {
  const requests = serve(() => [ACTIVE, AUTO, DISABLED]);
  const user = userEvent.setup();
  renderPage();

  // «Активные» first: the open ones only.
  expect(await screen.findByRole("tab", { name: "Активные" })).toHaveAttribute("aria-selected", "true");
  const active = await screen.findByRole("article", { name: "R1 Недосып" });
  expect(active).toHaveTextContent("активна");
  expect(active).toHaveTextContent(/Открыта 10\.10\.2026/);
  expect(screen.queryByRole("article", { name: "R2 Мало шагов" })).not.toBeInTheDocument();

  // «История»: closed automatically and closed because the rule was turned off.
  await user.click(screen.getByRole("tab", { name: "История" }));
  const auto = await screen.findByRole("article", { name: "R2 Мало шагов" });
  expect(auto).toHaveTextContent("закрыта автоматически");
  expect(auto).toHaveTextContent(/Открыта 05\.10\.2026/);
  expect(auto).toHaveTextContent(/Закрыта 08\.10\.2026/);
  const disabled = screen.getByRole("article", { name: "R3 Повышенный пульс в покое" });
  expect(disabled).toHaveTextContent("правило отключено");
  expect(screen.queryByRole("article", { name: "R1 Недосып" })).not.toBeInTheDocument();

  // The filter by rule asks the API for that rule only.
  await user.selectOptions(screen.getByRole("combobox", { name: "Правило" }), "R3");
  await waitFor(() =>
    expect(screen.queryByRole("article", { name: "R2 Мало шагов" })).not.toBeInTheDocument(),
  );
  expect(screen.getByRole("article", { name: "R3 Повышенный пульс в покое" })).toBeInTheDocument();
  expect(requests).toContain("status=open");
  expect(requests).toContain("status=resolved&status=closed_rule_disabled");
  expect(requests).toContain("status=resolved&status=closed_rule_disabled&rule=R3");
});

test("feedback buttons reflect saved value", async () => {
  let current = ACTIVE;
  const calls: { method: string; body: unknown; csrf: string | null }[] = [];
  serve(() => [current]);
  server.use(
    http.put("/api/recommendations/:id/feedback", async ({ request }) => {
      const body = (await request.json()) as { value: Feedback };
      calls.push({ method: "PUT", body, csrf: request.headers.get("X-Requested-With") });
      current = { ...current, feedback: body.value, feedback_at: "2026-10-11T08:00:00Z" };
      return HttpResponse.json(current);
    }),
    http.delete("/api/recommendations/:id/feedback", ({ request }) => {
      calls.push({ method: "DELETE", body: null, csrf: request.headers.get("X-Requested-With") });
      current = { ...current, feedback: null, feedback_at: null };
      return HttpResponse.json(current);
    }),
  );
  const user = userEvent.setup();
  renderPage();

  const card = await screen.findByRole("article", { name: "R1 Недосып" });
  const useful = within(card).getByRole("button", { name: "Полезно" });
  const notUseful = within(card).getByRole("button", { name: "Не полезно" });
  // The saved value.
  expect(useful).toHaveAttribute("aria-pressed", "true");
  expect(notUseful).toHaveAttribute("aria-pressed", "false");

  // Changed…
  await user.click(notUseful);
  await waitFor(() => expect(notUseful).toHaveAttribute("aria-pressed", "true"));
  expect(useful).toHaveAttribute("aria-pressed", "false");

  // …and cleared by pressing the pressed one again.
  await user.click(notUseful);
  await waitFor(() => expect(notUseful).toHaveAttribute("aria-pressed", "false"));
  expect(useful).toHaveAttribute("aria-pressed", "false");

  expect(calls).toEqual([
    { method: "PUT", body: { value: "not_useful" }, csrf: "ht" },
    { method: "DELETE", body: null, csrf: "ht" },
  ]);
});

test("disclaimer is shown", async () => {
  serve(() => []);
  renderPage();

  const note = await screen.findByRole("note");
  expect(note).toHaveTextContent("носят информационный характер");
  expect(note).toHaveTextContent("не заменяют консультацию врача");
  // An empty tab says so.
  expect(await screen.findByText("Активных рекомендаций нет.")).toBeInTheDocument();
});
