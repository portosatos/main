import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { server } from "@/test/server";

import App from "./App";

const demo = {
  id: "6f1c7a52-8f0e-4e8e-9f3a-2a1d6b8c9e01",
  email: "demo@example.com",
  notify_email: null,
};

// A logged-in session that POST /api/auth/logout ends; not a dev stack (no dev panel).
function fakeSession() {
  let loggedIn = true;
  server.use(
    http.get("/api/auth/me", () =>
      loggedIn
        ? HttpResponse.json(demo)
        : HttpResponse.json({ detail: "Не авторизован" }, { status: 401 }),
    ),
    http.post("/api/auth/logout", () => {
      loggedIn = false;
      return new HttpResponse(null, { status: 204 });
    }),
    http.get("/api/dev/clock", () => HttpResponse.json({ detail: "Not Found" }, { status: 404 })),
  );
}

afterEach(() => window.history.replaceState(null, "", "/"));

test("renders app shell with title «Трекер здоровья»", async () => {
  fakeSession();
  render(<App />);

  const banner = await screen.findByRole("banner");
  expect(within(banner).getByRole("heading", { level: 1, name: "Трекер здоровья" })).toBeVisible();
  expect(within(banner).getByText("demo@example.com")).toBeInTheDocument();
  const menu = screen.getByRole("navigation", { name: "Разделы" });
  const labels = ["Дашборд", "Загрузка", "Устройства", "Цели", "Рекомендации", "Правила", "Настройки"];
  for (const label of labels) {
    expect(within(menu).getByRole("link", { name: label })).toBeInTheDocument();
  }
});

test("logout leads to the login page", async () => {
  fakeSession();
  const user = userEvent.setup();
  render(<App />);

  await user.click(await screen.findByRole("button", { name: "Выйти" }));

  expect(await screen.findByRole("heading", { name: "Вход" })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/login");
});
