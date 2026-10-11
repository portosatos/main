// API client (SPEC F1): same-origin requests with the session cookie, the CSRF header on every
// mutating request, and a redirect to /login when the session is gone.

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

type Navigate = (to: string) => void;

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

// Until the app registers its router, a full page load does the redirect.
let redirect: Navigate = (to) => window.location.assign(to);

// The app passes its router here, so a 401 becomes an in-app navigation.
export function setUnauthorizedRedirect(navigate: Navigate): void {
  redirect = navigate;
}

// The session is gone: to /login. Also for requests made without apiFetch (the upload XHR).
export function onUnauthorized(): void {
  redirect("/login");
}

export async function apiFetch<T>(
  path: string,
  init: { method?: string; body?: unknown } = {},
): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers({ Accept: "application/json" });
  if (!SAFE_METHODS.has(method)) headers.set("X-Requested-With", "ht");
  if (init.body !== undefined) headers.set("Content-Type", "application/json");

  // An absolute URL: the same origin in the browser, and Node's fetch in tests needs one.
  const response = await fetch(new URL(path, window.location.href), {
    method,
    headers,
    credentials: "include",
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });

  if (!response.ok) {
    const detail = await readDetail(response);
    // A 401 from /api/auth/* is an answer for the form (wrong password) or for ProtectedRoute.
    if (response.status === 401 && !path.startsWith("/api/auth/")) onUnauthorized();
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function readDetail(response: Response): Promise<unknown> {
  try {
    const body: unknown = await response.json();
    return body !== null && typeof body === "object" && "detail" in body ? body.detail : body;
  } catch {
    return null;
  }
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "POST", body }),
  put: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "PUT", body }),
  patch: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "PATCH", body }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
};
