import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { renderRoutes } from "@/test/render";
import { server } from "@/test/server";

import Register from "./Register";

const routes = [
  { path: "/register", element: <Register /> },
  { path: "/", element: <p>Главная страница</p> },
];

afterEach(() => vi.restoreAllMocks());

test.fails("sends browser timezone", async () => {
  // A zone that is neither the machine's nor UTC, so a hardcoded value cannot pass.
  const real = new Intl.DateTimeFormat().resolvedOptions();
  vi.spyOn(Intl.DateTimeFormat.prototype, "resolvedOptions").mockReturnValue({
    ...real,
    timeZone: "America/Argentina/Ushuaia",
  });
  let body: unknown;
  server.use(
    http.post("/api/auth/register", async ({ request }) => {
      body = await request.json();
      return HttpResponse.json(
        { id: "0b8d1d0e-3c55-4a5e-8d47-5d7f1f2f0a11", email: "new@example.com", notify_email: null },
        { status: 201 },
      );
    }),
  );
  const user = userEvent.setup();
  renderRoutes(routes, ["/register"]);

  await user.type(await screen.findByLabelText("Email"), "new@example.com");
  await user.type(screen.getByLabelText("Пароль"), "secret-pass");
  await user.click(screen.getByRole("button", { name: "Зарегистрироваться" }));

  expect(await screen.findByText("Главная страница")).toBeInTheDocument();
  expect(body).toEqual({
    email: "new@example.com",
    password: "secret-pass",
    timezone: "America/Argentina/Ushuaia",
  });
});

test.fails("rejects a password shorter than 8 characters", async () => {
  const user = userEvent.setup();
  renderRoutes(routes, ["/register"]);

  await user.type(await screen.findByLabelText("Email"), "new@example.com");
  await user.type(screen.getByLabelText("Пароль"), "short");
  await user.click(screen.getByRole("button", { name: "Зарегистрироваться" }));

  expect(await screen.findByText("Пароль — не меньше 8 символов")).toBeInTheDocument();
});
