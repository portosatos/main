import { MAILPIT_URL } from "./env";

export type MailpitMessage = {
  ID: string;
  Subject: string;
  To: { Address: string }[];
  Created: string;
};

// A whole letter: `Date` is its Date header — the server's Clock at the send, not Mailpit's.
export type MailpitLetter = {
  ID: string;
  Subject: string;
  Date: string;
  Text: string;
  HTML: string;
};

// Letters in the e2e Mailpit (its API, SPEC §5): digests of one recipient, newest first.
export const mailpit = {
  async messages(to: string): Promise<MailpitMessage[]> {
    const query = new URLSearchParams({ query: `to:"${to}"` });
    const response = await fetch(`${MAILPIT_URL}/api/v1/search?${query}`);
    if (!response.ok) throw new Error(`Mailpit search: HTTP ${response.status}`);
    const body = (await response.json()) as { messages: MailpitMessage[] | null };
    // The search is by substring; keep the exact recipient only.
    return (body.messages ?? []).filter((message) =>
      message.To.some((address) => address.Address.toLowerCase() === to.toLowerCase()),
    );
  },

  // The letter with its text and HTML.
  async message(id: string): Promise<MailpitLetter> {
    const response = await fetch(`${MAILPIT_URL}/api/v1/message/${encodeURIComponent(id)}`);
    if (!response.ok) throw new Error(`Mailpit message ${id}: HTTP ${response.status}`);
    return (await response.json()) as MailpitLetter;
  },

  // Waits until the recipient has `count` letters (fails on more) and returns them, newest first.
  async waitFor(to: string, count: number, timeoutMs = 30_000): Promise<MailpitMessage[]> {
    const deadline = Date.now() + timeoutMs;
    for (;;) {
      const messages = await mailpit.messages(to);
      if (messages.length > count) {
        throw new Error(`${to} has ${messages.length} letters, expected ${count}`);
      }
      if (messages.length === count) return messages;
      if (Date.now() > deadline) {
        throw new Error(`${to} has ${messages.length} letters after ${timeoutMs} ms, expected ${count}`);
      }
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  },
};
