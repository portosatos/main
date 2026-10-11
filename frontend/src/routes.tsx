import type { ReactNode } from "react";
import { Navigate, type RouteObject } from "react-router";

import AppLayout from "@/components/AppLayout";
import ProtectedRoute from "@/components/ProtectedRoute";
import { sections } from "@/lib/sections";
import Devices from "@/pages/Devices";
import Login from "@/pages/Login";
import Placeholder from "@/pages/Placeholder";
import Register from "@/pages/Register";
import Upload from "@/pages/Upload";

// Sections whose page is ready; the rest show a placeholder.
const pages: Partial<Record<string, ReactNode>> = {
  "/upload": <Upload />,
  "/devices": <Devices />,
};

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
          element: pages[section.to] ?? <Placeholder title={section.label} />,
        })),
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
];
