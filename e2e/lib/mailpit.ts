import { MAILPIT_URL } from "./env";

export type MailpitMessage = {
  ID: string;
  Subject: string;
  To: { Address: string }[];
  Created: string;
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
};
