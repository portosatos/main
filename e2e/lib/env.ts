import path from "node:path";

// Where the e2e stack listens (docker-compose.e2e.yml): the app behind nginx and Mailpit's API.
export const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:5174";
export const MAILPIT_URL = process.env.E2E_MAILPIT_URL ?? "http://localhost:8026";

// Users of the scenarios live in this zone, and htgen writes their files in it (its default).
export const TIMEZONE = "Europe/Moscow";

export const REPO_ROOT = path.resolve(import.meta.dirname, "..", "..");

// The digest dispatcher's tick in the e2e stack (DIGEST_TICK_S of docker-compose.e2e.yml): a letter
// that is due goes within one tick, and "no letter" is checked after two.
export const DIGEST_TICK_MS = 5_000;

// Every mutating request to the API carries it, otherwise 403 (ADR-026).
export const CSRF_HEADERS = { "X-Requested-With": "ht" };
