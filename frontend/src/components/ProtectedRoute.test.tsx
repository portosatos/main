import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { renderRoutes } from "@/test/render";
import { server } from "@/test/server";

import ProtectedRoute from "./ProtectedRoute";

test("unauthenticated user is redirected", async () => {
  server.use(
    http.get("/api/auth/me", () => HttpResponse.json({ detail: "Не авторизован" }, { status: 401 })),
  );

  renderRoutes(
    [
      { element: <ProtectedRoute />, children: [{ path: "/", element: <p>Закрытая страница</p> }] },
      { path: "/login", element: <p>Страница входа</p> },
    ],
    ["/"],
  );

  expect(await screen.findByText("Страница входа")).toBeInTheDocument();
  expect(screen.queryByText("Закрытая страница")).not.toBeInTheDocument();
});
