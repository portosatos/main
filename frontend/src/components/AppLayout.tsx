import { NavLink, Outlet, useNavigate } from "react-router";

import { useLogout, useMe } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { sections } from "@/lib/sections";

// The shell of the logged-in app: header with the menu, the user and logout.
export default function AppLayout() {
  const me = useMe();
  const navigate = useNavigate();
  const logout = useLogout(() => navigate("/login", { replace: true }));

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
          <h1 className="text-lg font-semibold">Трекер здоровья</h1>
          <div className="ml-auto flex min-w-0 items-center gap-3">
            <span className="truncate text-sm text-muted-foreground">{me.data?.email}</span>
            <Button
              variant="outline"
              size="sm"
              disabled={logout.isPending}
              onClick={() => logout.mutate()}
            >
              Выйти
            </Button>
          </div>
          <nav aria-label="Разделы" className="w-full">
            <ul className="flex flex-wrap gap-1">
              {sections.map((section) => (
                <li key={section.to}>
                  <NavLink
                    to={section.to}
                    end
                    className={({ isActive }) =>
                      `block rounded-md px-3 py-1.5 text-sm hover:bg-accent ${
                        isActive ? "bg-accent font-medium" : "text-muted-foreground"
                      }`
                    }
                  >
                    {section.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
