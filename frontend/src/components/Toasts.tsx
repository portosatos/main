import { Toaster } from "sonner";

// The toasts of the tab (SPEC F8, F12): useEvents shows them on server events (lib/toasts.ts);
// every open tab gets the event, so every tab shows the toast.
export default function Toasts() {
  return <Toaster position="top-center" richColors closeButton duration={6000} />;
}
