import { Navigate, type RouteObject } from "react-router";

import AppLayout from "@/components/AppLayout";
import ProtectedRoute from "@/components/ProtectedRoute";
import { sections } from "@/lib/sections";
import Login from "@/pages/Login";
import Placeholder from "@/pages/Placeholder";
import Register from "@/pages/Register";

export const routes: RouteObject[] = [
  { path: "/login", element: <Login /> },
  { path: "/register", element: <Register /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: sections.map((section) => ({
          path: section.to,
          element: <Placeholder title={section.label} />,
        })),
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
];
