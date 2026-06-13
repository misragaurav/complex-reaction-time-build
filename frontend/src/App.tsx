import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { RequireRole } from "./auth/RequireRole";
import { identityRole, roleHome } from "./auth/types";
import Layout from "./components/Layout";
import AccountPage from "./pages/AccountPage";
import AdminUsersPage from "./pages/AdminUsersPage";
import LoginPage from "./pages/LoginPage";
import MySessionsPage from "./pages/MySessionsPage";
import StudiesListPage from "./pages/StudiesListPage";
import StudyDetailPage from "./pages/StudyDetailPage";
import StudyPreviewPage from "./pages/StudyPreviewPage";
import TaskRunnerPage from "./pages/TaskRunnerPage";

function RootRedirect(): JSX.Element {
  const { identity, status } = useAuth();

  if (status === "loading") {
    return <div className="flex h-screen items-center justify-center text-sm text-gray-500">Loading…</div>;
  }

  if (!identity) {
    return <Navigate to="/login" replace />;
  }

  return <Navigate to={roleHome(identityRole(identity))} replace />;
}

function AppRoutes(): JSX.Element {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/run/:sessionId"
        element={
          <RequireRole roles={["participant"]}>
            <TaskRunnerPage />
          </RequireRole>
        }
      />

      {/* Like /run, the preview runs fullscreen outside the app chrome. */}
      <Route
        path="/studies/:id/preview"
        element={
          <RequireRole roles={["admin", "researcher"]}>
            <StudyPreviewPage />
          </RequireRole>
        }
      />

      <Route element={<Layout />}>
        <Route
          path="/me"
          element={
            <RequireRole roles={["participant"]}>
              <MySessionsPage />
            </RequireRole>
          }
        />
        <Route
          path="/account"
          element={
            <RequireRole roles={["admin", "researcher"]}>
              <AccountPage />
            </RequireRole>
          }
        />
        <Route
          path="/studies"
          element={
            <RequireRole roles={["admin", "researcher"]}>
              <StudiesListPage />
            </RequireRole>
          }
        />
        <Route
          path="/studies/:id"
          element={
            <RequireRole roles={["admin", "researcher"]}>
              <StudyDetailPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin/users"
          element={
            <RequireRole roles={["admin"]}>
              <AdminUsersPage />
            </RequireRole>
          }
        />
      </Route>

      <Route path="/" element={<RootRedirect />} />
      <Route path="*" element={<RootRedirect />} />
    </Routes>
  );
}

export default function App(): JSX.Element {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
