import { http, HttpResponse } from "msw";

import { server } from "@/test/server";

import { api, setUnauthorizedRedirect } from "./client";

test.fails("adds X-Requested-With on mutating requests", async () => {
  const seen: Record<string, string | null> = {};
  server.use(
    http.all("/api/things", ({ request }) => {
      seen[request.method] = request.headers.get("X-Requested-With");
      return new HttpResponse(null, { status: 204 });
    }),
  );

  await api.get("/api/things");
  await api.post("/api/things", { a: 1 });
  await api.put("/api/things", { a: 2 });
  await api.patch("/api/things", { a: 3 });
  await api.delete("/api/things");

  expect(Object.keys(seen)).toContain("GET");
  expect(seen).toMatchObject({ POST: "ht", PUT: "ht", PATCH: "ht", DELETE: "ht" });
});

test.fails("sends the session cookie with every request", async () => {
  let credentials: RequestCredentials | undefined;
  server.use(
    http.get("/api/things", ({ request }) => {
      credentials = request.credentials;
      return HttpResponse.json([]);
    }),
  );

  await api.get("/api/things");

  expect(credentials).toBe("include");
});

test.fails("redirects to /login on 401", async () => {
  const navigate = vi.fn();
  setUnauthorizedRedirect(navigate);
  server.use(
    http.get("/api/goals", () => HttpResponse.json({ detail: "Не авторизован" }, { status: 401 })),
  );

  await expect(api.get("/api/goals")).rejects.toMatchObject({ status: 401 });
  expect(navigate).toHaveBeenCalledWith("/login");
});

test.fails("does not redirect on 401 from /api/auth/* (the form shows the error)", async () => {
  const navigate = vi.fn();
  setUnauthorizedRedirect(navigate);
  server.use(
    http.post("/api/auth/login", () =>
      HttpResponse.json({ detail: "Неверный email или пароль" }, { status: 401 }),
    ),
  );

  await expect(api.post("/api/auth/login", {})).rejects.toMatchObject({
    status: 401,
    detail: "Неверный email или пароль",
  });
  expect(navigate).not.toHaveBeenCalled();
});
