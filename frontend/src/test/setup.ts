import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";

import { server } from "./server";

// jsdom has no ResizeObserver; Recharts' ResponsiveContainer needs one (it keeps its initial size).
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Any request without a handler fails the test: the UI must not reach a real backend.
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
});
afterAll(() => server.close());
