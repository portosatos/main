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
  async message(_id: string): Promise<MailpitLetter> {
    throw new Error("step 12.2: not implemented");
  },

  // Waits until the recipient has `count` letters (fails on more) and returns them, newest first.
  async waitFor(_to: string, _count: number, _timeoutMs?: number): Promise<MailpitMessage[]> {
    throw new Error("step 12.2: not implemented");
  },
};
