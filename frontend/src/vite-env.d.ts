/// <reference types="vite/client" />

interface ImportMetaEnv {
  // Mailpit UI for the dev panel; by default the same host, port 8025.
  readonly VITE_MAILPIT_URL?: string;
}
