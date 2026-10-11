import { http, HttpResponse, type RequestHandler } from "msw";

// Default API mocks for all tests; a test adds its own with server.use(...).
export const handlers: RequestHandler[] = [
  // The logged-in user, in UTC unless a test says otherwise.
  http.get("/api/auth/me", () =>
    HttpResponse.json({
      id: "u",
      email: "demo@example.com",
      notify_email: "demo@example.com",
      today: "2026-10-11",
      timezone: "UTC",
    }),
  ),
  // The dev panel's digest queue: empty unless a test says otherwise.
  http.get("/api/digests", () =>
    HttpResponse.json({
      notify_email: null,
      warning: null,
      pending: 0,
      items: [],
    }),
  ),
];
