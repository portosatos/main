import { Navigate, Outlet, useLocation } from "react-router";

import { useMe } from "@/api/auth";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/button";

// Pages inside need a session: without one (/api/auth/me → 401) the user goes to /login and
// comes back here after logging in.
export default function ProtectedRoute() {
  const me = useMe();
  const location = useLocation();

  if (me.isPending) {
    return (
      <div role="status" className="p-6 text-sm text-muted-foreground">
        Загрузка…
      </div>
    );
  }
  if (me.isError) {
    if (me.error instanceof ApiError && me.error.status === 401) {
      return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
    }
    return (
      <div role="alert" className="grid justify-items-start gap-3 p-6 text-sm">
        <p>Не удалось связаться с сервером.</p>
        <Button variant="outline" onClick={() => void me.refetch()}>
          Повторить
        </Button>
      </div>
    );
  }
  return <Outlet />;
}
