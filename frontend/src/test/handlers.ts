import type { RequestHandler } from "msw";

// Default API mocks for all tests; a test adds its own with server.use(...).
export const handlers: RequestHandler[] = [];
