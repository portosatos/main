import { Bell as BellIcon } from "lucide-react";

import { Button } from "@/components/ui/button";

// The bell in the header (SPEC §6.4, F8): the unread count and the feed.
// Step 7.2 stub: the button only.
export default function Bell() {
  return (
    <Button variant="ghost" size="icon" aria-label="Уведомления">
      <BellIcon aria-hidden />
    </Button>
  );
}
