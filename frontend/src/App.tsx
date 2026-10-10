import { QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { createBrowserRouter, RouterProvider } from "react-router";

import { setUnauthorizedRedirect } from "@/api/client";
import { createQueryClient } from "@/lib/queryClient";
import { routes } from "@/routes";

// The app: query cache, router, and a 401 from any API call leads to /login.
export default function App() {
  const [queryClient] = useState(createQueryClient);
  const [router] = useState(() => createBrowserRouter(routes));

  useEffect(() => {
    setUnauthorizedRedirect((to) => {
      void router.navigate(to, { replace: true });
      queryClient.clear();
    });
  }, [queryClient, router]);

  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
