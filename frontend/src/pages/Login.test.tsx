import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { renderRoutes } from "@/test/render";
import { server } from "@/test/server";

import Login from "./Login";

const routes = [
  { path: "/login", element: <Login /> },
  { path: "/", element: <p>Главная страница</p> },
];

const demo = {
  id: "6f1c7a52-8f0e-4e8e-9f3a-2a1d6b8c9e01",
  email: "demo@example.com",
  notify_email: null,
};

test.fails("shows validation errors in Russian", async () => {
  const user = userEvent.setup();
  renderRoutes(routes, ["/login"]);

  await user.click(await screen.findByRole("button", { name: "Войти" }));
  expect(await screen.findByText("Введите email")).toBeInTheDocument();
  expect(screen.getByText("Введите пароль")).toBeInTheDocument();

  await user.type(screen.getByLabelText("Email"), "not-an-email");
  await user.click(screen.getByRole("button", { name: "Войти" }));
  expect(await screen.findByText("Некорректный email")).toBeInTheDocument();
});

test.fails("navigates to / after successful login", async () => {
  let body: unknown;
  server.use(
    http.post("/api/auth/login", async ({ request }) => {
      body = await request.json();
      return HttpResponse.json(demo);
    }),
  );
  const user = userEvent.setup();
  renderRoutes(routes, ["/login"]);

  await user.type(await screen.findByLabelText("Email"), "demo@example.com");
  await user.type(screen.getByLabelText("Пароль"), "demo12345");
  await user.click(screen.getByRole("button", { name: "Войти" }));

  expect(await screen.findByText("Главная страница")).toBeInTheDocument();
  expect(body).toEqual({ email: "demo@example.com", password: "demo12345" });
});

test.fails("shows the server message on wrong password", async () => {
  server.use(
    http.post("/api/auth/login", () =>
      HttpResponse.json({ detail: "Неверный email или пароль" }, { status: 401 }),
    ),
  );
  const user = userEvent.setup();
  renderRoutes(routes, ["/login"]);

  await user.type(await screen.findByLabelText("Email"), "demo@example.com");
  await user.type(screen.getByLabelText("Пароль"), "wrong-password");
  await user.click(screen.getByRole("button", { name: "Войти" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Неверный email или пароль");
  expect(screen.queryByText("Главная страница")).not.toBeInTheDocument();
});
