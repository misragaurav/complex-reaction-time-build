import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { identityRole, roleHome, type Role } from "./types";

interface RequireRoleProps {
  roles: Role[];
  children: JSX.Element;
}

export function RequireRole({ roles, children }: RequireRoleProps): JSX.Element {
  const { identity, status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <div className="flex h-screen items-center justify-center text-sm text-gray-500">Loading…</div>;
  }

  if (!identity) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  const role = identityRole(identity);
  if (!roles.includes(role)) {
    return <Navigate to={roleHome(role)} replace />;
  }

  return children;
}
