import type { ReactNode } from "react";
import { Navigate, type RouteObject } from "react-router";

import AppLayout from "@/components/AppLayout";
import ProtectedRoute from "@/components/ProtectedRoute";
import { sections } from "@/lib/sections";
import Dashboard from "@/pages/Dashboard";
import Devices from "@/pages/Devices";
import Goals from "@/pages/Goals";
import Login from "@/pages/Login";
import Placeholder from "@/pages/Placeholder";
import Recommendations from "@/pages/Recommendations";
import Register from "@/pages/Register";
import Rules from "@/pages/Rules";
import Upload from "@/pages/Upload";

// Sections whose page is ready; the rest show a placeholder.
const pages: Partial<Record<string, ReactNode>> = {
  "/": <Dashboard />,
  "/upload": <Upload />,
  "/devices": <Devices />,
  "/goals": <Goals />,
  "/recommendations": <Recommendations />,
  "/rules": <Rules />,
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
