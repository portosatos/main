export type MailpitMessage = {
  ID: string;
  Subject: string;
  To: { Address: string }[];
  Created: string;
};

// Letters in the e2e Mailpit (its API, SPEC §5): digests of one recipient, newest first.
export const mailpit = {
  async messages(to: string): Promise<MailpitMessage[]> {
    void to;
    throw new Error("step 12.1: not implemented");
  },
};
