import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { identityRole } from "../auth/types";
import { Button } from "./forms";

function navLinkClass({ isActive }: { isActive: boolean }): string {
  return `rounded-md px-3 py-2 text-sm font-medium ${
    isActive ? "bg-gray-900 text-white" : "text-gray-700 hover:bg-gray-100"
  }`;
}

export default function Layout(): JSX.Element {
  const { identity, logout } = useAuth();
  const navigate = useNavigate();

  if (!identity) {
    return <Outlet />;
  }

  const role = identityRole(identity);
  const displayName = identity.kind === "user" ? identity.full_name : identity.code;

  const handleLogout = (): void => {
    void logout().then(() => navigate("/login", { replace: true }));
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-6">
            <span className="text-lg font-semibold text-gray-900">CRT Lab</span>
            <nav className="flex gap-1">
              {role === "participant" && (
                <NavLink to="/me" className={navLinkClass}>
                  My sessions
                </NavLink>
              )}
              {(role === "admin" || role === "researcher") && (
                <NavLink to="/studies" className={navLinkClass}>
                  Studies
                </NavLink>
              )}
              {role === "admin" && (
                <NavLink to="/admin/users" className={navLinkClass}>
                  Users
                </NavLink>
              )}
              {(role === "admin" || role === "researcher") && (
                <NavLink to="/account" className={navLinkClass}>
                  Account
                </NavLink>
              )}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500">{displayName}</span>
            <Button variant="secondary" onClick={handleLogout}>
              Log out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
