import { Outlet } from "react-router";

// Stub: lets everyone through; the session check comes with step 1.3.
export default function ProtectedRoute() {
  return <Outlet />;
}
